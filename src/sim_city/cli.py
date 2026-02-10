"""SimCity CLI - AI-powered startup simulation engine."""
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
from sim_city.config import ensure_directories, LOG_LEVEL, DATA_DIR, BASE_DIR
from sim_city.models import SimulationEntity, SimulationStage
from sim_city.storage import TinyDBStorageManager
from sim_city.engine.core import SimulationEngine
from sim_city.engine.spawner import generate_initial_agents
from sim_city.agent.factory import create_agent_instance
from sim_city.llm.factory import LLMFactory
from sim_city.llm.cache import CachedLLMProvider
from sim_city.events import Event
from sim_city.dashboard import SimulationDashboard, KeyboardListener
from sim_city.agent.learning import inject_lessons_into_agent
from sim_city.analytics import compare_simulations, export_json, export_csv, risk_assessment
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
app = typer.Typer(name="sim-city", help="AI-powered startup simulation engine.", add_completion=True, rich_markup_mode="rich")
simulate_app = typer.Typer(help="Manage simulations")
app.add_typer(simulate_app, name="simulate")
console = Console()
TEMPLATES_DIR = BASE_DIR / "configs" / "templates"

@app.callback()
def main():
    """SimCity: AI-powered startup simulation engine."""
    ensure_directories()

@simulate_app.command("new")
def new_simulation(
    name: str = typer.Option(None, prompt="Startup Name"),
    industry: str = typer.Option(None, prompt="Industry (e.g. Fintech, AI, SaaS)"),
    description: str = typer.Option(None, prompt="Product Description"),
    stage: str = typer.Option("idea", prompt="Current Stage (idea, mvp, launch, growth)"),
    template: Optional[str] = typer.Option(None, help="Use a template (saas, marketplace, fintech, hardware)"),
):
    """Create a new simulation."""
    storage = TinyDBStorageManager()
    if template:
        tpl_path = TEMPLATES_DIR / f"{template}.toml"
        if tpl_path.exists():
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            tpl = tomllib.loads(tpl_path.read_text())
            sim_cfg = tpl.get("simulation", {})
            name = name or sim_cfg.get("name", "Unnamed")
            industry = industry or sim_cfg.get("industry", "General")
            description = description or sim_cfg.get("description", "")
            stage = stage or sim_cfg.get("stage", "idea")
            console.print(f"[cyan]Using template: {template}[/cyan]")
        else:
            console.print(f"[yellow]Template '{template}' not found. Available: {', '.join(p.stem for p in TEMPLATES_DIR.glob('*.toml'))}[/yellow]")
    sim_id = str(uuid.uuid4())
    stage_enum = SimulationStage(stage.lower())
    simulation = SimulationEntity(id=sim_id, name=name, description=description, industry=industry, stage=stage_enum, parameters={}, created_at=time.time())
    storage.create_simulation(simulation)
    console.print(f"[green]Created simulation: {name} ({sim_id})[/green]")
    agents = generate_initial_agents(simulation)
    for agent in agents:
        storage.save_agent(sim_id, agent)
        console.print(f" - Spawned agent: [bold]{agent.name}[/bold] ({agent.role})")
    console.print(f"\n[bold]Ready to run![/bold] Use: [cyan]sim-city simulate run {sim_id}[/cyan]")

@simulate_app.command("run")
def run_simulation(
    simulation_id: str = typer.Argument(..., help="ID of the simulation to run"),
    model: str = typer.Option("ollama:llama3", help="LLM Provider"),
    speed: float = typer.Option(1.0, help="Simulation speed multiplier"),
    duration: int = typer.Option(100, help="Number of ticks to run"),
    resume: bool = typer.Option(False, help="Resume from last checkpoint"),
    headless: bool = typer.Option(False, help="Headless mode"),
    cache: bool = typer.Option(False, help="Cache LLM responses"),
):
    """Run an existing simulation."""
    storage = TinyDBStorageManager()
    simulation = storage.get_simulation(simulation_id)
    if not simulation:
        if not headless:
            console.print(f"[red]Simulation {simulation_id} not found![/red]")
        raise typer.Exit(code=1)
    engine = SimulationEngine(simulation, storage)
    engine.speed_multiplier = speed
    try:
        llm = LLMFactory.create(model)
        if cache:
            llm = CachedLLMProvider(llm)
    except Exception as e:
        if not headless:
            console.print(f"[red]Failed to initialize LLM: {e}[/red]")
        raise typer.Exit(code=1)
    agent_entities = storage.get_agents(simulation_id)
    for entity in agent_entities:
        agent_instance = create_agent_instance(entity=entity, event_bus=engine.event_bus, llm_provider=llm, world_context={"id": simulation.id, "name": simulation.name, "description": simulation.description, "industry": simulation.industry, "stage": simulation.stage.value})
        engine.spawn_agent(agent_instance)
    for agent in engine.agents:
        inject_lessons_into_agent(agent, storage, simulation_id)
    if resume:
        restored = engine.restore_from_checkpoint()
        if not headless:
            console.print(f"[green]Restored at tick {engine.tick_count}[/green]" if restored else "[yellow]No checkpoint, starting fresh.[/yellow]")
    if headless:
        engine.run_loop(max_ticks=duration)
        return
    dash = SimulationDashboard(console, simulation_name=simulation.name)
    dash.agents = [{"id": a.entity.id, "name": a.entity.name, "role": a.entity.role, "type": a.entity.type.value} for a in engine.agents]
    engine.event_bus.subscribe("tick", dash.on_tick)
    engine.event_bus.subscribe("interaction_occurred", dash.on_interaction)
    engine.event_bus.subscribe("metric_changed", dash.on_metric)
    engine.event_bus.subscribe("simulation_paused", dash.on_pause)
    engine.event_bus.subscribe("simulation_resumed", dash.on_resume)
    engine.event_bus.subscribe("simulation_stopped", dash.on_stop)
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
    storage = TinyDBStorageManager()
    simulation = storage.get_simulation(simulation_id)
    if not simulation:
        console.print(f"[red]Simulation {simulation_id} not found[/red]")
        raise typer.Exit(1)
    if agent_id:
        agents = storage.get_agents(simulation_id)
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
def status_simulation(simulation_id: str):
    """Show status of a simulation."""
    storage = TinyDBStorageManager()
    simulation = storage.get_simulation(simulation_id)
    if not simulation:
        console.print(f"[red]Simulation {simulation_id} not found[/red]")
        raise typer.Exit(1)
    agents = storage.get_agents(simulation_id)
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
def list_simulations():
    """List all simulations."""
    storage = TinyDBStorageManager()
    sims = storage.list_simulations()
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
    storage = TinyDBStorageManager()
    sims = storage.list_simulations()
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
    storage = TinyDBStorageManager()
    result = compare_simulations(storage, ids)
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
):
    """Show simulation interaction logs with filters."""
    storage = TinyDBStorageManager()
    interactions = storage.get_interactions(simulation_id)
    if agent:
        interactions = [i for i in interactions if i.agent_id == agent]
    if action_type:
        interactions = [i for i in interactions if i.action == action_type]
    interactions = interactions[-limit:]
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
):
    """Export simulation data as a JSON bundle."""
    storage = TinyDBStorageManager()
    simulation = storage.get_simulation(simulation_id)
    if not simulation:
        console.print(f"[red]Simulation {simulation_id} not found[/red]")
        raise typer.Exit(1)
    agents = storage.get_agents(simulation_id)
    interactions = storage.get_interactions(simulation_id)
    metrics = storage.get_metrics(simulation_id)
    bundle = {
        "simulation": simulation.to_dict(),
        "agents": [a.to_dict() for a in agents],
        "interactions": [i.to_dict() for i in interactions],
        "metrics": [m.to_dict() for m in metrics],
        "exported_at": time.time(),
    }
    out_path = Path(output) / f"{simulation.name.replace(' ', '_')}_{simulation_id[:8]}.json"
    export_json(bundle, out_path)
    console.print(f"[green]Exported to {out_path}[/green]")

@simulate_app.command("import")
def import_simulation(path: str = typer.Argument(..., help="Path to JSON bundle")):
    """Import a simulation from a JSON bundle."""
    storage = TinyDBStorageManager()
    data = json.loads(Path(path).read_text())
    sim = SimulationEntity.from_dict(data["simulation"])
    storage.create_simulation(sim)
    from sim_city.models import AgentEntity
    for a in data.get("agents", []):
        storage.save_agent(sim.id, AgentEntity.from_dict(a))
    console.print(f"[green]Imported simulation: {sim.name} ({sim.id})[/green]")

@simulate_app.command("tutorial")
def tutorial():
    """Interactive tutorial with sample simulation."""
    console.print(Panel(
        "[bold]Welcome to SimCity Tutorial![/bold]\n\n"
        "SimCity simulates startup ecosystems using AI agents.\n"
        "Each agent (customer, investor, competitor, etc.) makes\n"
        "autonomous decisions based on their role and personality.\n\n"
        "[cyan]Quick Start:[/cyan]\n"
        "1. Create: [bold]sim-city simulate new --template saas[/bold]\n"
        "2. Run:    [bold]sim-city simulate run <id> --model mock --speed 100[/bold]\n"
        "3. View:   [bold]sim-city simulate status <id>[/bold]\n"
        "4. Logs:   [bold]sim-city simulate logs <id>[/bold]\n"
        "5. Compare:[bold]sim-city simulate compare <id1> <id2>[/bold]\n\n"
        "[dim]Templates: saas, marketplace, fintech, hardware[/dim]\n"
        "[dim]Models: ollama:llama3, openai:gpt-4o, anthropic:claude-3-opus, mock[/dim]",
        title="Tutorial", border_style="cyan"
    ))

if __name__ == "__main__":
    app()
