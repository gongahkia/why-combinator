"""Why-Combinator CLI - AI-powered startup simulation engine."""
import typer
import time
import uuid
import json
import logging
from typing import Optional, List
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from datetime import datetime
from why_combinator.config import ensure_directories, configure_logging, LOG_LEVEL, DATA_DIR, BASE_DIR
from why_combinator.models import SimulationEntity, SimulationStage
from why_combinator.dashboard import SimulationDashboard, KeyboardListener
import why_combinator.api as api

# Default logging setup - will be reconfigured by flags
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
app = typer.Typer(name="why-combinator", help="AI-powered startup simulation engine.", add_completion=True, rich_markup_mode="rich")
simulate_app = typer.Typer(help="Manage simulations")
app.add_typer(simulate_app, name="simulate")
console = Console()
TEMPLATES_DIR = BASE_DIR / "configs" / "templates"

@app.callback()
def main():
    """Why-Combinator: AI-powered startup simulation engine."""
    ensure_directories()

@simulate_app.command("new")
def new_simulation(
    name: str = typer.Option(None, prompt="Startup Name"),
    industry: str = typer.Option(None, prompt="Industry (e.g. Fintech, AI, SaaS)"),
    description: str = typer.Option(None, prompt="Product Description"),
    stage: str = typer.Option("idea", prompt="Current Stage (idea, mvp, launch, growth)"),
    template: Optional[str] = typer.Option(None, help="Use a template (saas, marketplace, fintech, hardware)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate config and print agent roster without persisting"),
):
    """Create a new simulation."""
    template_data = None
    if template:
        tpl_path = TEMPLATES_DIR / f"{template}.toml"
        if tpl_path.exists():
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            template_data = tomllib.loads(tpl_path.read_text())
            console.print(f"[cyan]Using template: {template}[/cyan]")
        else:
            console.print(f"[yellow]Template '{template}' not found. Available: {', '.join(p.stem for p in TEMPLATES_DIR.glob('*.toml'))}[/yellow]")
    
    if dry_run:
        # Dry run mode: validate config and print agent roster without persisting
        console.print(f"[cyan]DRY RUN MODE - No data will be saved[/cyan]\n")
        console.print(f"[bold]Simulation Config:[/bold]")
        console.print(f"  Name: {name}")
        console.print(f"  Industry: {industry}")
        console.print(f"  Description: {description}")
        console.print(f"  Stage: {stage}")
        
        # Temporarily create simulation to generate agents
        from why_combinator.engine.spawner import generate_initial_agents
        from why_combinator.models import SimulationEntity, SimulationStage
        temp_sim = SimulationEntity(
            id="dry-run-temp",
            name=name,
            description=description,
            industry=industry,
            stage=SimulationStage(stage.lower()),
            parameters=template_data.get("parameters", {}) if template_data else {},
            created_at=time.time()
        )
        agents = generate_initial_agents(temp_sim)
        console.print(f"\n[bold]Agent Roster ({len(agents)} agents):[/bold]")
        for agent in agents:
            console.print(f"  - {agent.name} ({agent.role}) - {agent.type.value}")
        console.print(f"\n[green]Validation passed. Run without --dry-run to create.[/green]")
        return
    
    simulation = api.create_simulation(
        name=name,
        industry=industry,
        description=description,
        stage=stage,
        template_data=template_data
    )
    
    console.print(f"[green]Created simulation: {simulation.name} ({simulation.id})[/green]")
    agents = api.get_agents(simulation.id)
    for agent in agents:
        console.print(f" - Spawned agent: [bold]{agent.name}[/bold] ({agent.role})")
    console.print(f"\n[bold]Ready to run![/bold] Use: [cyan]why-combinator simulate run {simulation.id}[/cyan]")

@simulate_app.command("run")
def run_simulation(
    simulation_id: str = typer.Argument(..., help="ID of the simulation to run"),
    model: str = typer.Option("ollama:llama3", help="LLM Provider"),
    speed: float = typer.Option(1.0, help="Simulation speed multiplier"),
    duration: int = typer.Option(100, help="Number of ticks to run"),
    resume: bool = typer.Option(False, help="Resume from last checkpoint"),
    headless: bool = typer.Option(False, help="Headless mode"),
    cache: bool = typer.Option(False, help="Cache LLM responses"),
    seed: Optional[int] = typer.Option(None, help="Random seed for reproducible simulations"),
    parallel: bool = typer.Option(False, help="Run agent steps concurrently"),
    max_failures: Optional[int] = typer.Option(None, help="Stop after N consecutive agent failures"),
    log_format: str = typer.Option("human", "--log-format", help="Log format: 'human' or 'json'"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Override WHY_COMBINATOR_DATA_DIR for this run"),
):
    """Run an existing simulation."""
    # Configure logging based on --log-format flag
    configure_logging(format_type=log_format)
    
    # Override output directory if specified
    if output_dir:
        import os
        from why_combinator import config
        config.DATA_DIR = Path(output_dir).absolute()
        config.SIMULATIONS_DIR = config.DATA_DIR / "simulations"
        os.environ["WHY_COMBINATOR_DATA_DIR"] = str(config.DATA_DIR)
        ensure_directories()
        console.print(f"[cyan]Using output directory: {config.DATA_DIR}[/cyan]")
    
    if headless:
        try:
            report = api.run_simulation(
                simulation_id=simulation_id, 
                duration=duration, 
                model=model, 
                speed=speed, 
                resume=resume, 
                cache=cache, 
                seed=seed, 
                max_failures=max_failures, 
                headless=True
            )
            console.print(f"[bold]Simulation finished.[/bold]")
            return
        except Exception as e:
             console.print(f"[red]Simulation failed: {e}[/red]")
             raise typer.Exit(code=1)
            
    # Non-headless: Use API to setup, then drive UI locally
    try:
        engine = api.setup_simulation_engine(
            simulation_id=simulation_id,
            model=model,
            speed=speed,
            resume=resume,
            cache=cache,
            seed=seed,
            max_failures=max_failures
        )
    except Exception as e:
        console.print(f"[red]Failed to initialize simulation: {e}[/red]")
        raise typer.Exit(code=1)

    dash = SimulationDashboard(console, simulation_name=engine.simulation.name)
    dash.agents = [{"id": a.entity.id, "name": a.entity.name, "role": a.entity.role, "type": a.entity.type.value} for a in engine.agents]
    engine.event_bus.subscribe("tick", dash.on_tick)
    engine.event_bus.subscribe("interaction_occurred", dash.on_interaction)
    engine.event_bus.subscribe("metric_changed", dash.on_metric)
    engine.event_bus.subscribe("simulation_paused", dash.on_pause)
    engine.event_bus.subscribe("simulation_resumed", dash.on_resume)
    engine.event_bus.subscribe("simulation_stopped", dash.on_stop)
    engine.event_bus.subscribe("sentiment_update", dash.on_sentiment)
    kb = KeyboardListener(engine)
    with Live(dash.render(), console=console, refresh_per_second=4, transient=True) as live:
        dash.set_live(live)
        kb.start()
        try:
            engine.run_loop(max_ticks=duration)
        finally:
            kb.stop()
    console.print(f"[bold]Simulation finished at tick {engine.tick_count}.[/bold]")
    report = engine.finalize()
    console.print(Panel(
        f"Interactions: {report['total_interactions']}\n"
        f"Top Actions: {', '.join(f'{a[0]}({a[1]})' for a in report['top_actions'])}\n"
        f"Strengths: {', '.join(report['strengths']) or 'None identified'}\n"
        f"Weaknesses: {', '.join(report['weaknesses']) or 'None identified'}\n"
        f"Recommendation: [bold]{report['recommendation']}[/bold]",
        title="Critique Report", border_style="magenta"
    ))

@simulate_app.command("inspect")
def inspect_simulation(simulation_id: str = typer.Argument(...), agent_id: Optional[str] = typer.Option(None)):
    """Inspect simulation or agent details."""
    """Inspect simulation or agent details."""
    simulation = api.get_simulation(simulation_id)
    if not simulation:
        console.print(f"[red]Simulation {simulation_id} not found[/red]")
        raise typer.Exit(1)
        
    if agent_id:
        agents = api.get_agents(simulation_id)
        agent = next((a for a in agents if a.id == agent_id), None)
        if not agent:
            console.print(f"[red]Agent {agent_id} not found[/red]")
            return
        console.print(Panel(f"[bold]{agent.name}[/bold]\nRole: {agent.role}\nType: {agent.type.value}", title="Agent Details"))
        console.print(f"Personality: {agent.personality}")
        console.print(f"Knowledge: {agent.knowledge_base}")
    else:
        status_simulation(simulation_id)

@simulate_app.command("status")
def status_simulation(
    simulation_id: str = typer.Argument(...),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show status of a simulation."""
    from why_combinator.export import pipe_friendly_output
    """Show status of a simulation."""
    from why_combinator.export import pipe_friendly_output
    simulation = api.get_simulation(simulation_id)
    if not simulation:
        console.print(f"[red]Simulation {simulation_id} not found[/red]")
        raise typer.Exit(1)
    agents = api.get_agents(simulation_id)
    
    if json_output:
        data = {"simulation": simulation.to_dict(), "agents": [a.to_dict() for a in agents]}
        print(pipe_friendly_output(data))
        return
        
    console.print(Panel(
        f"ID: {simulation.id}\nName: {simulation.name}\nIndustry: {simulation.industry}\n"
        f"Stage: {simulation.stage.value}\nCreated: {datetime.fromtimestamp(simulation.created_at)}\nAgents: {len(agents)}",
        title="Simulation Status"
    ))
    table = Table(title="Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Role")
    table.add_column("Type")
    for agent in agents:
        table.add_row(agent.id, agent.name, agent.role, agent.type.value)
    console.print(table)

@simulate_app.command("list")
def list_simulations(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all simulations."""
    from why_combinator.export import pipe_friendly_output
    sims = api.list_simulations()
    if json_output:
        data = {"simulations": [s.to_dict() for s in sims]}
        print(pipe_friendly_output(data))
        return
    table = Table(title="Simulations")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Industry")
    table.add_column("Stage")
    for sim in sims:
        table.add_row(sim.id, sim.name, sim.industry, sim.stage.value)
    console.print(table)

@simulate_app.command("history")
def simulation_history():
    """Show simulation history sorted by creation date."""
    sims = api.list_simulations()
    sims.sort(key=lambda s: s.created_at, reverse=True)
    table = Table(title="Simulation History")
    table.add_column("Date", style="dim")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Industry")
    table.add_column("Stage")
    table.add_column("Ticks")
    for sim in sims:
        ticks = sim.parameters.get("tick_count", "?")
        table.add_row(datetime.fromtimestamp(sim.created_at).strftime("%Y-%m-%d %H:%M"), sim.id[:12] + "..", sim.name, sim.industry, sim.stage.value, str(ticks))
    console.print(table)

@simulate_app.command("compare")
def compare_sims(ids: List[str] = typer.Argument(..., help="Simulation IDs to compare")):
    """Compare two or more simulations."""
    result = api.compare_results(ids)
    if not result["simulations"]:
        console.print("[red]No valid simulations found.[/red]")
        return
    table = Table(title="Simulation Comparison")
    table.add_column("Metric", style="bold")
    for sim in result["simulations"]:
        table.add_column(sim["name"], style="cyan")
    table.add_row("Industry", *[s["industry"] for s in result["simulations"]])
    table.add_row("Stage", *[s["stage"] for s in result["simulations"]])
    table.add_row("Interactions", *[str(s["interactions"]) for s in result["simulations"]])
    for metric, values in result["metric_comparison"].items():
        table.add_row(metric, *[f"{values.get(s['name'], 0):.4f}" for s in result["simulations"]])
    console.print(table)

@simulate_app.command("logs")
def simulation_logs(
    simulation_id: str = typer.Argument(...),
    agent: Optional[str] = typer.Option(None, help="Filter by agent ID"),
    action_type: Optional[str] = typer.Option(None, "--type", help="Filter by action type"),
    limit: int = typer.Option(50, help="Max logs to show"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show simulation interaction logs with filters."""
    from why_combinator.export import pipe_friendly_output
    
    interactions = api.get_simulation_logs(
        simulation_id=simulation_id,
        agent_id=agent,
        action_type=action_type,
        limit=limit
    )
    if json_output:
        data = {"interactions": [i.to_dict() for i in interactions]}
        print(pipe_friendly_output(data))
        return
    table = Table(title=f"Logs ({len(interactions)} entries)")
    table.add_column("Time", style="dim")
    table.add_column("Agent", style="cyan")
    table.add_column("Action", style="bold")
    table.add_column("Target")
    table.add_column("Outcome")
    for i in interactions:
        table.add_row(datetime.fromtimestamp(i.timestamp).strftime("%H:%M:%S") if i.timestamp else "?", i.agent_id[:8] + "..", i.action, i.target, str(i.outcome)[:60])
    console.print(table)

@simulate_app.command("export")
def export_simulation(
    simulation_id: str = typer.Argument(...),
    output: str = typer.Option(".", help="Output directory"),
    fmt: str = typer.Option("json", "--format", help="Export format: json, csv, md, pdf"),
):
    """Export simulation data in various formats."""
    try:
        path = api.export_simulation(simulation_id, output, fmt)
        console.print(f"[green]Exported ({fmt}) to {path}*[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

@simulate_app.command("import")
def import_simulation(path: str = typer.Argument(..., help="Path to JSON bundle")):
    """Import a simulation from a JSON bundle."""
    try:
        sim = api.import_simulation(path)
        console.print(f"[green]Imported simulation: {sim.name} ({sim.id})[/green]")
    except Exception as e:
        console.print(f"[red]Import failed: {e}[/red]")
        raise typer.Exit(1)

@simulate_app.command("delete")
def delete_simulation(
    simulation_id: str = typer.Argument(..., help="ID of the simulation to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a simulation and its data."""
    sim = api.get_simulation(simulation_id)
    if not sim:
        console.print(f"[red]Simulation {simulation_id} not found[/red]")
        raise typer.Exit(1)
        
    if not yes:
        confirm = typer.confirm(f"Delete simulation '{sim.name}' ({simulation_id})?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return
            
    if api.delete_simulation(simulation_id):
        console.print(f"[green]Deleted simulation: {sim.name} ({simulation_id})[/green]")
    else:
        console.print(f"[red]Failed to delete simulation {simulation_id}[/red]")

@simulate_app.command("clone")
def clone_simulation(
    simulation_id: str = typer.Argument(..., help="ID of the simulation to clone"),
):
    """Deep-copy a simulation into a new ID for A/B testing."""
    try:
        cloned = api.clone_simulation(simulation_id)
        console.print(f"[green]Cloned simulation: {cloned.name} ({cloned.id})[/green]")
        console.print(f"  Original: {simulation_id}")
        console.print(f"  Clone:    {cloned.id}")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

@simulate_app.command("tutorial")
def tutorial(
    auto_run: bool = typer.Option(False, "--auto", help="Auto-create and run a sample simulation"),
):
    """Interactive tutorial with sample simulation."""
    console.print(Panel(
        "[bold]Welcome to Why-Combinator Tutorial![/bold]\n\n"
        "Why-Combinator simulates startup ecosystems using AI agents.\n"
        "Each agent (customer, investor, competitor, etc.) makes\n"
        "autonomous decisions based on their role and personality.\n\n"
        "[cyan]Quick Start:[/cyan]\n"
        "1. Create: [bold]why-combinator simulate new --template saas[/bold]\n"
        "2. Run:    [bold]why-combinator simulate run <id> --model mock --speed 100[/bold]\n"
        "3. View:   [bold]why-combinator simulate status <id>[/bold]\n"
        "4. Logs:   [bold]why-combinator simulate logs <id>[/bold]\n"
        "5. Compare:[bold]why-combinator simulate compare <id1> <id2>[/bold]\n\n"
        "[dim]Templates: saas, marketplace, fintech, hardware[/dim]\n"
        "[dim]Models: ollama:llama3, openai:gpt-4o, anthropic:claude-3-opus, mock[/dim]",
        title="Tutorial", border_style="cyan"
    ))
    if auto_run:
        console.print("\n[cyan]Auto-creating and running a sample simulation...[/cyan]")
        sim = api.create_simulation(
            name="Tutorial SaaS", 
            description="Sample B2B SaaS platform", 
            industry="SaaS", 
            stage="mvp", 
            parameters={"market_size": 1000000, "initial_capital": 500000}
        )
        
        console.print(f"[green]Created: {sim.name} ({sim.id})[/green]")
        console.print(f"[cyan]Running 20 ticks with mock provider...[/cyan]")
        
        report = api.run_simulation(
            simulation_id=sim.id,
            duration=20,
            model="mock",
            headless=True
        )
        
        console.print(f"\n[bold]Results after 20 ticks:[/bold]")
        console.print(f"  Interactions: {report['total_interactions']}")
        console.print(f"  Recommendation: [bold]{report['recommendation']}[/bold]")
        console.print(f"\n[dim]Explore with: why-combinator simulate status {sim.id}[/dim]")


@app.command("migrate")
def migrate_storage(
    from_backend: str = typer.Option(..., "--from", help="Source storage backend (tinydb)"),
    to_backend: str = typer.Option(..., "--to", help="Destination storage backend (sqlite)"),
):
    """Migrate simulation data between storage backends."""
    if from_backend == "tinydb" and to_backend == "sqlite":
        console.print("[cyan]Migrating from TinyDB to SQLite...[/cyan]")
        from why_combinator.storage import migrate_tinydb_to_sqlite
        try:
            migrate_tinydb_to_sqlite()
            console.print("[green]Migration completed successfully![/green]")
        except Exception as e:
            console.print(f"[red]Migration failed: {e}[/red]")
            raise typer.Exit(1)
    else:
        console.print(f"[red]Unsupported migration: {from_backend} -> {to_backend}[/red]")
        console.print("[yellow]Currently supported: --from tinydb --to sqlite[/yellow]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

