"""SimCity CLI - AI-powered startup simulation engine."""

import typer
import time
import uuid
import logging
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from datetime import datetime

from sim_city.config import ensure_directories, LOG_LEVEL
from sim_city.models import SimulationEntity, SimulationStage, SimulationRun
from sim_city.storage import TinyDBStorageManager
from sim_city.engine.core import SimulationEngine
from sim_city.engine.spawner import generate_initial_agents
from sim_city.agent.factory import create_agent_instance
from sim_city.llm.factory import LLMFactory
from sim_city.events import Event

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="sim-city",
    help="AI-powered startup simulation engine.",
    add_completion=True,
    rich_markup_mode="rich",
)
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
    
    # Create Simulation Entity
    sim_id = str(uuid.uuid4())
    stage_enum = SimulationStage(stage.lower())
    
    simulation = SimulationEntity(
        id=sim_id,
        name=name,
        description=description,
        industry=industry,
        stage=stage_enum,
        parameters={},
        created_at=time.time()
    )
    
    storage.create_simulation(simulation)
    console.print(f"[green]Created simulation: {name} ({sim_id})[/green]")
    
    # Generate Initial Agents
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
):
    """Run an existing simulation."""
    storage = TinyDBStorageManager()
    simulation = storage.get_simulation(simulation_id)
    
    if not simulation:
        console.print(f"[red]Simulation {simulation_id} not found![/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]Starting Simulation: {simulation.name}[/bold green]")
    console.print(f"Industry: {simulation.industry} | Stage: {simulation.stage.value}")
    console.print(f"Model: {model} | Speed: {speed}x\n")

    # Initialize Engine
    engine = SimulationEngine(simulation, storage)
    engine.speed_multiplier = speed
    
    # Load LLM Provider
    try:
        llm = LLMFactory.create(model)
    except Exception as e:
        console.print(f"[red]Failed to initialize LLM: {e}[/red]")
        raise typer.Exit(code=1)

    # Hydrate Agents
    agent_entities = storage.get_agents(simulation_id)
    for entity in agent_entities:
        agent_instance = create_agent_instance(
            entity=entity,
            event_bus=engine.event_bus,
            llm_provider=llm,
            world_context={
                "id": simulation.id,
                "name": simulation.name,
                "description": simulation.description,
                "industry": simulation.industry,
                "stage": simulation.stage.value
            }
        )
        engine.spawn_agent(agent_instance)

    # Event Listener for UI updates
    def on_tick(event: Event):
        # We can implement a richer UI here
        pass
        
    def on_interaction(event: Event):
        agent_id = event.payload.get("agent_id")
        action = event.payload.get("action")
        target = event.payload.get("target")
        outcome = event.payload.get("outcome", {})
        console.print(f"[cyan]{agent_id[:8]}..[/cyan] [bold]{action}[/bold] -> {target}: {str(outcome)[:100]}")

    engine.event_bus.subscribe("tick", on_tick)
    engine.event_bus.subscribe("interaction_occurred", on_interaction)

    # simple spinner or just run
    try:
        engine.run_loop(max_ticks=duration)
    except KeyboardInterrupt:
        console.print("[yellow]Simulation paused by user.[/yellow]")
    finally:
        engine.stop()


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
