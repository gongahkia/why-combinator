from typing import List, Dict, Any, Optional, Callable
import time
import asyncio
from datetime import datetime
import logging
from dataclasses import dataclass, field

from sim_city.models import SimulationEntity, SimulationRun, AgentEntity, InteractionLog, MetricSnapshot
from sim_city.events import EventBus
from sim_city.agent.base import BaseAgent
from sim_city.storage import StorageManager

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Core simulation orchestrator."""

    def __init__(self, simulation: SimulationEntity, storage: StorageManager):
        self.simulation = simulation
        self.storage = storage
        self.event_bus = EventBus()
        self.agents: List[BaseAgent] = []
        
        self.current_time = simulation.created_at  # Virtual timestamp start
        self.tick_count = 0
        self.is_running = False
        self.speed_multiplier = 1.0  # 1x real-time (1 sim sec = 1 real sec)
        
        # In-memory transient state
        self.world_state: Dict[str, Any] = {}

    def load_agents(self):
        """Load agents from storage or initialize empty."""
        agent_entities = self.storage.get_agents(self.simulation.id)
        # TODO: Hydrate these into BaseAgent instances via a factory
        # For now, just keep track of entities if we lack concrete classes
        # This will be updated when we implement Agent Factory
        pass

    def spawn_agent(self, agent: BaseAgent):
        """Add a new agent to the simulation."""
        self.agents.append(agent)
        self.storage.save_agent(self.simulation.id, agent.entity)
        self.event_bus.publish("agent_created", agent.entity.to_dict(), self.current_time)

    def start(self):
        """Start or resume the simulation loop."""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info(f"Simulation {self.simulation.id} started.")
        self.event_bus.publish("simulation_started", {"id": self.simulation.id}, self.current_time)
        
        # In a real app, this might run in a separate thread or async task
        # dependent on the implementation model (CLI blocking vs daemon)
        # For CLI MVP, we might block or use repeated calls to step()

    def stop(self):
        """Pause/Stop simulation."""
        self.is_running = False
        logger.info(f"Simulation {self.simulation.id} stopped.")
        self.event_bus.publish("simulation_stopped", {"id": self.simulation.id}, self.current_time)

    def step(self, duration: float = 1.0):
        """Advance simulation by one tick of `duration` seconds."""
        if not self.is_running:
            return

        self.tick_count += 1
        self.current_time += duration
        
        # 1. Update World State (e.g. market fluctuations)
        # TODO: Implement world physics/economy update
        date_str = datetime.fromtimestamp(self.current_time).strftime("%Y-%m-%d %H:%M:%S")
        self.world_state["date"] = date_str
        self.world_state["timestamp"] = self.current_time

        self.world_state["agents"] = [{"id": a.entity.id, "name": a.entity.name, "role": a.entity.role, "type": a.entity.type.value} for a in self.agents] # agent roster for inter-agent comms
        for agent in self.agents:
            interaction = agent.run_step(self.world_state, self.current_time)
            if interaction:
                self.storage.log_interaction(interaction)
        
        # 3. Emit tick event
        self.event_bus.publish("tick", {"tick": self.tick_count, "time": self.current_time}, self.current_time)

        # 4. Checkpoint periodically
        if self.tick_count % 100 == 0:
            self.checkpoint()

    def checkpoint(self):
        """Save current state to storage."""
        # Update simulation metadata
        # self.simulation.parameters['current_time'] = self.current_time
        # self.storage.create_simulation(self.simulation)  # Upsert logic needed?
        logger.info(f"Checkpoint saved at tick {self.tick_count}")

    def run_loop(self, max_ticks: Optional[int] = None):
        """Blocking run loop for CLI usage."""
        self.start()
        try:
            while self.is_running:
                start_real = time.time()
                
                self.step()
                
                if max_ticks and self.tick_count >= max_ticks:
                    self.stop()
                    break
                
                # Speed control
                # If speed_multiplier is 1.0, and step takes 0.1s, and step defined as 1.0s virtual
                # We should sleep 0.9s.
                # If speed is 1000x, we sleep 0.
                
                # Logic: Real time duration for 1 virtual second = 1.0 / self.speed_multiplier
                target_loop_duration = 1.0 / self.speed_multiplier
                elapsed = time.time() - start_real
                if elapsed < target_loop_duration:
                    time.sleep(target_loop_duration - elapsed)
                    
        except KeyboardInterrupt:
            self.stop()
