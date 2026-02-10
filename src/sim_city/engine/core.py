from typing import List, Dict, Any, Optional, Callable
import time
import signal
import threading
from datetime import datetime
import logging
from sim_city.models import SimulationEntity, SimulationRun, InteractionLog, MetricSnapshot
from sim_city.events import EventBus
from sim_city.agent.base import BaseAgent
from sim_city.storage import StorageManager
from sim_city.generation import calculate_basic_metrics, generate_critique_report
from sim_city.agent.relationships import RelationshipGraph

logger = logging.getLogger(__name__)

class SimulationEngine:
    """Core simulation orchestrator."""
    def __init__(self, simulation: SimulationEntity, storage: StorageManager):
        self.simulation = simulation
        self.storage = storage
        self.event_bus = EventBus()
        self.agents: List[BaseAgent] = []
        self.current_time = simulation.created_at
        self.tick_count = 0
        self.is_running = False
        self.is_paused = False
        self.speed_multiplier = 1.0
        self.world_state: Dict[str, Any] = {}
        self.relationships = RelationshipGraph()
        self._orig_sigint = None
        self._orig_sigterm = None
    def _install_signal_handlers(self):
        """Install signal handlers for graceful pause/stop."""
        self._orig_sigint = signal.getsignal(signal.SIGINT)
        self._orig_sigterm = signal.getsignal(signal.SIGTERM)
        self._sigint_count = 0
        def _handle_sigint(signum, frame):
            self._sigint_count += 1
            if self._sigint_count == 1:
                if self.is_paused:
                    self.resume()
                else:
                    self.pause()
            else: # second ctrl-c = hard stop
                self.stop()
        signal.signal(signal.SIGINT, _handle_sigint)
        signal.signal(signal.SIGTERM, lambda s, f: self.stop())
    def _restore_signal_handlers(self):
        if self._orig_sigint:
            signal.signal(signal.SIGINT, self._orig_sigint)
        if self._orig_sigterm:
            signal.signal(signal.SIGTERM, self._orig_sigterm)
    def spawn_agent(self, agent: BaseAgent):
        self.agents.append(agent)
        self.storage.save_agent(self.simulation.id, agent.entity)
        self.event_bus.publish("agent_created", agent.entity.to_dict(), self.current_time)
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.is_paused = False
        logger.info(f"Simulation {self.simulation.id} started.")
        self.event_bus.publish("simulation_started", {"id": self.simulation.id}, self.current_time)
    def stop(self):
        self.is_running = False
        self.is_paused = False
        logger.info(f"Simulation {self.simulation.id} stopped.")
        self.event_bus.publish("simulation_stopped", {"id": self.simulation.id}, self.current_time)
    def pause(self):
        if self.is_running and not self.is_paused:
            self.is_paused = True
            logger.info(f"Simulation {self.simulation.id} paused at tick {self.tick_count}.")
            self.event_bus.publish("simulation_paused", {"id": self.simulation.id, "tick": self.tick_count}, self.current_time)
    def resume(self):
        if self.is_running and self.is_paused:
            self.is_paused = False
            self._sigint_count = 0 # reset so next ctrl-c pauses again
            logger.info(f"Simulation {self.simulation.id} resumed.")
            self.event_bus.publish("simulation_resumed", {"id": self.simulation.id, "tick": self.tick_count}, self.current_time)
    def step(self, duration: float = 1.0):
        if not self.is_running or self.is_paused:
            return
        self.tick_count += 1
        self.current_time += duration
        date_str = datetime.fromtimestamp(self.current_time).strftime("%Y-%m-%d %H:%M:%S")
        self.world_state["date"] = date_str
        self.world_state["timestamp"] = self.current_time
        self.world_state["agents"] = [{"id": a.entity.id, "name": a.entity.name, "role": a.entity.role, "type": a.entity.type.value} for a in self.agents]
        for agent in self.agents:
            interaction = agent.run_step(self.world_state, self.current_time)
            if interaction:
                self.storage.log_interaction(interaction)
                self.relationships.update_from_interaction(interaction.agent_id, interaction.target, interaction.action)
        self.event_bus.publish("tick", {"tick": self.tick_count, "time": self.current_time, "date": date_str}, self.current_time)
        if self.tick_count % 10 == 0: # calculate metrics every 10 ticks
            self._emit_metrics()
        if self.tick_count % 100 == 0:
            self.checkpoint()
    def checkpoint(self):
        self.simulation.parameters["current_time"] = self.current_time
        self.simulation.parameters["tick_count"] = self.tick_count
        self.simulation.parameters["agent_memories"] = {a.entity.id: a.memory[-20:] for a in self.agents} # last 20 memories per agent
        db = self.storage._get_db(self.simulation.id)
        meta = db.table("metadata")
        meta.truncate()
        meta.insert(self.simulation.to_dict())
        logger.info(f"Checkpoint saved at tick {self.tick_count}")
    def restore_from_checkpoint(self):
        """Restore engine state from last checkpoint if available."""
        params = self.simulation.parameters
        if "current_time" in params:
            self.current_time = params["current_time"]
            self.tick_count = params.get("tick_count", 0)
            agent_mems = params.get("agent_memories", {})
            for agent in self.agents:
                if agent.entity.id in agent_mems:
                    agent.memory = agent_mems[agent.entity.id]
            logger.info(f"Restored from checkpoint at tick {self.tick_count}")
            return True
        return False
    def _emit_metrics(self):
        """Calculate and emit current metrics."""
        interactions = self.storage.get_interactions(self.simulation.id)
        metrics = calculate_basic_metrics(self.simulation, interactions, self.tick_count)
        for metric_type, value in metrics.items():
            snapshot = MetricSnapshot(simulation_id=self.simulation.id, timestamp=self.current_time, metric_type=metric_type, value=value)
            self.storage.log_metric(snapshot)
            self.event_bus.publish("metric_changed", {"metric_type": metric_type, "value": value}, self.current_time)
        self._latest_metrics = metrics
    def finalize(self) -> Dict[str, Any]:
        """Generate end-of-simulation critique report."""
        interactions = self.storage.get_interactions(self.simulation.id)
        metrics = getattr(self, "_latest_metrics", calculate_basic_metrics(self.simulation, interactions, self.tick_count))
        return generate_critique_report(self.simulation, interactions, metrics)
    def run_loop(self, max_ticks: Optional[int] = None):
        """Blocking run loop for CLI usage."""
        self._install_signal_handlers()
        self.start()
        try:
            while self.is_running:
                if self.is_paused:
                    time.sleep(0.1) # spin-wait while paused
                    continue
                start_real = time.time()
                self.step()
                if max_ticks and self.tick_count >= max_ticks:
                    self.stop()
                    break
                target_loop_duration = 1.0 / self.speed_multiplier
                elapsed = time.time() - start_real
                if elapsed < target_loop_duration:
                    time.sleep(target_loop_duration - elapsed)
        finally:
            self._restore_signal_handlers()
            if self.is_running:
                self.stop()
