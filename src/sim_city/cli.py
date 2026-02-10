"""SimCity CLI - AI-powered startup simulation engine."""
import typer
import time
import uuid
import logging
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from datetime import datetime
from sim_city.config import ensure_directories, LOG_LEVEL
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
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
app = typer.Typer(name="sim-city", help="AI-powered startup simulation engine.", add_completion=True, rich_markup_mode="rich")
simulate_app = typer.Typer(help="Manage simulations")
app.add_typer(simulate_app, name="simulate")
console = Console()

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
):
    """Create a new simulation."""
    storage = TinyDBStorageManager()
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
    model: str = typer.Option("ollama:llama3", help="LLM Provider (e.g. ollama:llama3, openai:gpt-4o)"),
    speed: float = typer.Option(1.0, help="Simulation speed multiplier"),
    duration: int = typer.Option(100, help="Number of ticks to run"),
    resume: bool = typer.Option(False, help="Resume from last checkpoint"),
    headless: bool = typer.Option(False, help="Headless mode - suppress interactive output"),
    cache: bool = typer.Option(False, help="Cache LLM responses to disk"),
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
        agent_instance = create_agent_instance(
            entity=entity, event_bus=engine.event_bus, llm_provider=llm,
            world_context={"id": simulation.id, "name": simulation.name, "description": simulation.description, "industry": simulation.industry, "stage": simulation.stage.value}
        )
        engine.spawn_agent(agent_instance)
    for agent in engine.agents: # inject lessons from past runs
        inject_lessons_into_agent(agent, storage, simulation_id)
    if resume:
        restored = engine.restore_from_checkpoint()
        if not headless:
            console.print(f"[green]Restored at tick {engine.tick_count}[/green]" if restored else "[yellow]No checkpoint, starting fresh.[/yellow]")
    if headless:
        engine.run_loop(max_ticks=duration)
        return
    # interactive mode with Rich Live dashboard
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
def inspect_simulation(
    simulation_id: str = typer.Argument(..., help="ID of the simulation"),
    agent_id: Optional[str] = typer.Option(None, help="Specific Agent ID to inspect"),
):
    """Inspect simulation details or a specific agent."""
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

if __name__ == "__main__":
    app()
