"""
Public API for Why-Combinator Simulation Engine.
This module provides high-level functions to manage and run simulations programmatically.
"""
import time
import uuid
import json
import logging
from typing import List, Dict, Any, Optional, Protocol
from pathlib import Path

from why_combinator.models import SimulationEntity, SimulationStage, AgentEntity, InteractionLog
from why_combinator.storage import TinyDBStorageManager, StorageManager
from why_combinator.engine.core import SimulationEngine
from why_combinator.engine.spawner import generate_initial_agents
from why_combinator.agent.factory import create_agent_instance
from why_combinator.llm.factory import LLMFactory
from why_combinator.llm.cache import CachedLLMProvider
from why_combinator.agent.learning import inject_lessons_into_agent
from why_combinator.analytics import compare_simulations as analytics_compare
from why_combinator.export import export_json_report, export_csv_report, export_markdown_report, export_pdf_report
from why_combinator.config import ensure_directories

logger = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """Protocol for library consumers to receive simulation progress updates."""
    
    def on_tick(self, tick: int, metrics: Dict[str, Any]) -> None:
        """Called after each simulation tick with current metrics."""
        ...
    
    def on_phase_change(self, phase: str) -> None:
        """Called when the simulation transitions to a new phase."""
        ...
    
    def on_complete(self, summary: Dict[str, Any]) -> None:
        """Called when the simulation completes."""
        ...

def _get_storage() -> StorageManager:
    ensure_directories()
    return TinyDBStorageManager()

def create_simulation(
    name: str,
    industry: str,
    description: str,
    stage: str = "idea",
    parameters: Optional[Dict[str, Any]] = None,
    template_data: Optional[Dict[str, Any]] = None
) -> SimulationEntity:
    """Create a new simulation and initial agents."""
    storage = _get_storage()
    sim_params = parameters or {}
    
    if template_data:
        sim_cfg = template_data.get("simulation", {})
        name = name or sim_cfg.get("name", "Unnamed")
        industry = industry or sim_cfg.get("industry", "General")
        description = description or sim_cfg.get("description", "")
        stage = stage or sim_cfg.get("stage", "idea")
        sim_params.update(template_data.get("parameters", {}))
        
    sim_id = str(uuid.uuid4())
    try:
        stage_enum = SimulationStage(stage.lower())
    except ValueError:
        stage_enum = SimulationStage.IDEA
        
    simulation = SimulationEntity(
        id=sim_id,
        name=name,
        description=description,
        industry=industry,
        stage=stage_enum,
        parameters=sim_params,
        created_at=time.time()
    )
    
    storage.create_simulation(simulation)
    
    # Generate agents
    agents = generate_initial_agents(simulation)
    for agent in agents:
        storage.save_agent(sim_id, agent)
        
    return simulation

def list_simulations() -> List[SimulationEntity]:
    """List all available simulations."""
    storage = _get_storage()
    return storage.list_simulations()

def get_simulation(simulation_id: str) -> Optional[SimulationEntity]:
    """Retrieve a simulation by ID."""
    storage = _get_storage()
    return storage.get_simulation(simulation_id)

def get_agents(simulation_id: str) -> List[AgentEntity]:
    """Retrieve all agents for a simulation."""
    storage = _get_storage()
    return storage.get_agents(simulation_id)

def setup_simulation_engine(
    simulation_id: str,
    model: str = "ollama:llama3",
    speed: float = 1.0,
    resume: bool = False,
    cache: bool = False,
    seed: Optional[int] = None,
    max_failures: Optional[int] = None,
    progress_callback: Optional[ProgressCallback] = None
) -> SimulationEngine:
    """Initialize and configure a simulation engine."""
    import random as _random
    if seed is not None:
        _random.seed(seed)
        
    storage = _get_storage()
    simulation = storage.get_simulation(simulation_id)
    if not simulation:
        raise ValueError(f"Simulation {simulation_id} not found")
        
    engine = SimulationEngine(simulation, storage, seed=seed, progress_callback=progress_callback)
    engine.speed_multiplier = speed
    if max_failures is not None:
        engine._max_failures = max_failures
        
    # Setup LLM
    try:
        llm = LLMFactory.create(model)
        if cache or seed is not None:
            llm = CachedLLMProvider(llm)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize LLM: {e}")
        
    # Load and spawn agents
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
        
    # Inject gathered lessons
    for agent in engine.agents:
        inject_lessons_into_agent(agent, storage, simulation_id)
        
    if resume:
        engine.restore_from_checkpoint()
        
    return engine

def run_simulation(
    simulation_id: str,
    duration: int = 100,
    model: str = "ollama:llama3",
    speed: float = 1.0,
    resume: bool = False,
    cache: bool = False,
    seed: Optional[int] = None,
    max_failures: Optional[int] = None,
    headless: bool = True,
    on_tick: Optional[Any] = None, # Deprecated - use progress_callback instead
    progress_callback: Optional[ProgressCallback] = None
) -> Dict[str, Any]:
    """Run a simulation for a specified duration."""
    engine = setup_simulation_engine(
        simulation_id=simulation_id,
        model=model,
        speed=speed,
        resume=resume,
        cache=cache,
        seed=seed,
        max_failures=max_failures,
        progress_callback=progress_callback
    )
    
    try:
        engine.run_loop(max_ticks=duration)
        return engine.finalize()
        
    except Exception as e:
        logger.exception("Simulation run failed")
        raise e
    finally:
        if engine.is_running:
            engine.stop()

def get_simulation_logs(
    simulation_id: str, 
    agent_id: Optional[str] = None, 
    action_type: Optional[str] = None, 
    limit: int = 50
) -> List[InteractionLog]:
    """Retrieve interaction logs with filtering."""
    storage = _get_storage()
    interactions = storage.get_interactions(simulation_id)
    
    if agent_id:
        interactions = [i for i in interactions if i.agent_id == agent_id]
    if action_type:
        interactions = [i for i in interactions if i.action == action_type]
        
    return interactions[-limit:]

def delete_simulation(simulation_id: str) -> bool:
    """Delete a simulation."""
    storage = _get_storage()
    sim = storage.get_simulation(simulation_id)
    if not sim:
        return False
        
    db_path = storage._get_db_path(simulation_id)
    if db_path.exists():
        db_path.unlink()
    return True

def clone_simulation(simulation_id: str) -> SimulationEntity:
    """Clone a simulation."""
    import copy
    storage = _get_storage()
    simulation = storage.get_simulation(simulation_id)
    if not simulation:
        raise ValueError(f"Simulation {simulation_id} not found")
        
    new_id = str(uuid.uuid4())
    cloned = copy.deepcopy(simulation)
    cloned.id = new_id
    cloned.name = f"{simulation.name} (clone)"
    cloned.created_at = time.time()
    cloned.parameters.pop("current_time", None)
    cloned.parameters.pop("tick_count", None)
    
    storage.create_simulation(cloned)
    
    agents = storage.get_agents(simulation_id)
    for agent in agents:
        cloned_agent = copy.deepcopy(agent)
        cloned_agent.id = str(uuid.uuid4())
        storage.save_agent(new_id, cloned_agent)
        
    return cloned

def export_simulation(simulation_id: str, output_dir: str, fmt: str = "json") -> str:
    """Export simulation data."""
    storage = _get_storage()
    simulation = storage.get_simulation(simulation_id)
    if not simulation:
        raise ValueError(f"Simulation {simulation_id} not found")
        
    out_path = Path(output_dir)
    if not out_path.exists():
        out_path.mkdir(parents=True, exist_ok=True)
        
    base = out_path / f"{simulation.name.replace(' ', '_')}_{simulation_id[:8]}"
    
    metrics_list = storage.get_metrics(simulation_id)
    latest_metrics = {m.metric_type: m.value for m in metrics_list}
    
    generated_file = ""
    if fmt == "json":
        generated_file = base.with_suffix(".json")
        export_json_report(storage, simulation_id, generated_file)
    elif fmt == "csv":
        generated_file = base.with_suffix(".csv")
        export_csv_report(storage, simulation_id, generated_file)
    elif fmt == "md":
        generated_file = base.with_suffix(".md")
        export_markdown_report(storage, simulation_id, generated_file, latest_metrics)
    elif fmt == "pdf":
        generated_file = base.with_suffix(".pdf")
        export_pdf_report(storage, simulation_id, generated_file, latest_metrics)
    else:
        raise ValueError(f"Unknown format: {fmt}")
        
    return str(generated_file)

def import_simulation(path: str) -> SimulationEntity:
    """Import a simulation from JSON."""
    storage = _get_storage()
    data = json.loads(Path(path).read_text())
    sim = SimulationEntity.from_dict(data["simulation"])
    storage.create_simulation(sim)
    
    for a in data.get("agents", []):
        storage.save_agent(sim.id, AgentEntity.from_dict(a))
        
    return sim

def compare_results(sim_ids: List[str]) -> Dict[str, Any]:
    """Compare multiple simulations."""
    storage = _get_storage()
    return analytics_compare(storage, sim_ids)
