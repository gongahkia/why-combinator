from typing import List, Dict, Any, Optional, Callable
import time
import signal
import threading
from datetime import datetime
import logging
from why_combinator.models import SimulationEntity, SimulationRun, InteractionLog, MetricSnapshot, WorldState
from why_combinator.events import EventBus
from why_combinator.agent.base import BaseAgent
from why_combinator.storage import StorageManager
from why_combinator.models import SimulationEntity, MetricSnapshot, ExperimentConfig
from why_combinator.llm.factory import LLMFactory
from why_combinator.llm.cache import CachedLLMProvider
from why_combinator.agent.impl import GenericAgent
from why_combinator.engine.spawner import generate_initial_agents
from dataclasses import asdict
import random
import uuid
from why_combinator.generation import calculate_basic_metrics, generate_critique_report
from why_combinator.agent.relationships import RelationshipGraph
from why_combinator.agent.emergence import EmergenceDetector
from why_combinator.agent.sentiment import SentimentTracker
from why_combinator.agent.coalition import CoalitionManager
from why_combinator.agent.conversation import ConversationManager
from why_combinator.agent.debate import DebateSession
from why_combinator.engine.scenarios import MultiPhaseManager, EventGenerator, CompetitiveMarket, get_seasonal_multiplier, MarketSaturation
from why_combinator.engine.performance import BatchWriter, AgentPool

logger = logging.getLogger(__name__)

class SimulationEngine:
    """Core simulation orchestrator."""
    def __init__(self, simulation: SimulationEntity, storage: StorageManager, seed: Optional[int] = None):
        self.simulation = simulation
        self.storage = storage
        
        # Handle RNG seeding for reproducibility
        if seed is not None:
            self.simulation.parameters["seed"] = seed
        
        sim_seed = self.simulation.parameters.get("seed")
        if sim_seed is not None:
            import random
            random.seed(sim_seed)
            logger.info(f"Simulation seeded with: {sim_seed}")
        self.event_bus = EventBus()
        self.agents: List[BaseAgent] = []
        self.current_time = simulation.created_at
        self.tick_count = 0
        self.is_running = False
        self.is_paused = False
        self.speed_multiplier = 1.0
        self.speed_multiplier = 1.0
        self.world_state: WorldState = WorldState(
            id=simulation.id,
            tick=0,
            date=str(datetime.fromtimestamp(self.current_time)),
            timestamp=self.current_time,
            stage=simulation.stage.value,
            metrics={},
            agents=[],
            sentiments={},
            relationships={},
            emergence_events=[],
            active_events=[]
        )
        self.relationships = RelationshipGraph()
        self.emergence_detector = EmergenceDetector()
        self.sentiment_tracker = SentimentTracker()
        self.coalition_manager = CoalitionManager()
        self.phase_manager = MultiPhaseManager(simulation, self.event_bus)
        self.event_generator = EventGenerator(self.event_bus)
        self.competitive_market = CompetitiveMarket()
        self._batch_writer = BatchWriter(storage)
        self._agent_pool: Optional[AgentPool] = None
        self._interaction_count_at_last_emit = 0
        self._cached_interactions: List[InteractionLog] = []
        self._llm_provider = None
        self._max_failures: Optional[int] = None
        self._consecutive_failures = 0
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
        if self._llm_provider is None and hasattr(agent, "llm_provider"):
            self._llm_provider = agent.llm_provider
        # Use AgentPool for large simulations
        if len(self.agents) > 20 and self._agent_pool is None:
            self._agent_pool = AgentPool(max_active=20)
            for a in self.agents:
                self._agent_pool.add(a)
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
        self._batch_writer.flush()
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
        self.world_state.tick = self.tick_count
        self.world_state.timestamp = self.current_time
        self.world_state.date = date_str
        self.world_state.stage = self.simulation.stage.value
        self.world_state.agents = [{"id": a.entity.id, "name": a.entity.name, "role": a.entity.role, "type": a.entity.type.value} for a in self.agents]
        # Inject simulation parameters into world_state
        # self.world_state.parameters = self.simulation.parameters # WorldState does not have parameters field defined yet, ignoring or need to add it?
        # The WorldState definition I added didn't have parameters.
        # But BaseAgent/GenericAgent might rely on it?
        # GenericAgent logic doesn't seem to use world_state["parameters"].
        
        # EventGenerator: probabilistic crises/macro/disruptions
        event = self.event_generator.maybe_trigger(self.tick_count)
        if event:
            self.world_state.active_events = [event]
        else:
            self.world_state.active_events = []
            
        # CompetitiveMarket: contest market share each tick
        current_share = getattr(self, "_latest_metrics", {}).get("market_share", 0.1)
        market_result = self.competitive_market.simulate_step(current_share)
        # self.world_state["market"] = market_result # WorldState doesn't have market field.
        # This was unused in GenericAgent anyway based on my read.
        
        # Inject emergence flags and sentiment into world_state
        self.world_state.emergence_events = self.emergence_detector.get_flags(since_tick=max(0, len(self.emergence_detector.action_history) - 20))
        self.world_state.sentiments = self.sentiment_tracker.get_all_sentiments()
        
        # Inject current metrics (runway, adoption, churn, revenue, burn)
        # Note: These are from the last 10-tick emit cycle, so might be slightly stale.
        self.world_state.metrics = getattr(self, "_latest_metrics", {})
        
        # Use AgentPool if available, otherwise all agents
        active_agents = self._agent_pool.get_active() if self._agent_pool else self.agents
        if self._agent_pool:
            self._agent_pool.rotate()
        for agent in active_agents:
            try:
                interaction = agent.run_step(self.world_state, self.current_time)
            except Exception as e:
                logger.error(f"Agent {agent.entity.id} step failed: {e}")
                self._consecutive_failures += 1
                if self._max_failures and self._consecutive_failures >= self._max_failures:
                    logger.error(f"Max failures ({self._max_failures}) reached, stopping simulation.")
                    self.stop()
                    return
                continue
            if interaction:
                self._consecutive_failures = 0
                self._batch_writer.add(interaction)
                self._cached_interactions.append(interaction)
                self.relationships.update_from_interaction(interaction.agent_id, interaction.target, interaction.action)
                self.emergence_detector.observe(interaction)
                self.sentiment_tracker.record_action(interaction.agent_id, interaction.action, str(interaction.outcome), self.current_time)
        self.event_bus.publish("tick", {"tick": self.tick_count, "time": self.current_time, "date": date_str}, self.current_time)
        if self.tick_count % 10 == 0:
            self._emit_metrics()
            # Publish sentiment data to dashboard
            self.event_bus.publish("sentiment_update", {"sentiments": self.sentiment_tracker.get_all_sentiments()}, self.current_time)
            # Publish emergence flags to dashboard
            new_flags = self.emergence_detector.get_flags(since_tick=max(0, len(self.emergence_detector.action_history) - 20))
            if new_flags:
                self.event_bus.publish("emergence_flags", {"flags": new_flags}, self.current_time)
            # MultiPhaseManager: check phase transitions
            metrics = getattr(self, "_latest_metrics", {})
            self.phase_manager.check_transition(self.tick_count, metrics)
        # CoalitionManager: detect coalitions every 50 ticks
        if self.tick_count % 50 == 0:
            agent_ids = [a.entity.id for a in self.agents]
            coalitions = self.coalition_manager.detect_coalitions(self.relationships, agent_ids)
            if coalitions:
                self.event_bus.publish("coalitions_detected", {"coalitions": [c.to_dict() for c in coalitions]}, self.current_time)
        # ConversationManager: trigger conversations between allies every 25 ticks
        if self.tick_count % 25 == 0 and self._llm_provider:
            for agent in self.agents:
                allies = self.relationships.get_allies(agent.entity.id)
                if allies:
                    ally_agents = [a for a in self.agents if a.entity.id in allies[:2]]
                    if ally_agents:
                        conv_mgr = ConversationManager(self._llm_provider)
                        conv_mgr.trigger_conversation([agent] + ally_agents, topic=f"Strategy discussion about {self.simulation.name}")
        # DebateSession: trigger debates between rivals every 50 ticks
        if self.tick_count % 50 == 0 and self._llm_provider:
            for agent in self.agents:
                rivals = self.relationships.get_rivals(agent.entity.id)
                if rivals:
                    rival_agents = [a for a in self.agents if a.entity.id in rivals[:1]]
                    if rival_agents:
                        debate = DebateSession(topic=f"Market direction for {self.simulation.industry}", context=f"Stage: {self.simulation.stage.value}", llm_provider=self._llm_provider, rounds=2)
                        debate.run([agent] + rival_agents)
                    break  # one debate per tick cycle
        
        # Apply relationship decay
        decay = self.simulation.parameters.get("relationship_decay_factor", 0.995)
        self.relationships.tick(decay)
        
        if self.tick_count % 100 == 0:
            self.checkpoint()
    def checkpoint(self):
        self.simulation.parameters["current_time"] = self.current_time
        self.simulation.parameters["tick_count"] = self.tick_count
        self.simulation.parameters["agent_memories"] = {a.entity.id: a.memory[-20:] for a in self.agents}
        self.simulation.parameters["relationships"] = self.relationships.to_dict()
        self.simulation.parameters["emergence_state"] = {"action_history": self.emergence_detector.action_history[-100:], "flags": self.emergence_detector.flags[-50:]}
        self.simulation.parameters["sentiment_history"] = {aid: entries[-50:] for aid, entries in self.sentiment_tracker._history.items()}
        self.simulation.parameters["coalitions"] = self.coalition_manager.to_dict()
        db = self.storage._get_db(self.simulation.id)
        meta = db.table("metadata")
        meta.truncate()
        meta.insert(self.simulation.to_dict())
        db.close()
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
            if "relationships" in params:
                self.relationships.from_dict(params["relationships"])
            if "emergence_state" in params:
                self.emergence_detector.action_history = params["emergence_state"].get("action_history", [])
                self.emergence_detector.flags = params["emergence_state"].get("flags", [])
            if "sentiment_history" in params:
                from collections import defaultdict
                self.sentiment_tracker._history = defaultdict(list, {aid: [tuple(e) for e in entries] for aid, entries in params["sentiment_history"].items()})
            if "coalitions" in params:
                from why_combinator.agent.coalition import Coalition
                self.coalition_manager.coalitions = [Coalition(name=c["name"], members=set(c["members"])) for c in params["coalitions"]]
            # Reload cached interactions for incremental metrics
            self._cached_interactions = self.storage.get_interactions(self.simulation.id)
            logger.info(f"Restored from checkpoint at tick {self.tick_count}")
            return True
        return False
    def _emit_metrics(self):
        """Calculate and emit current metrics with seasonal multipliers using cached interactions."""
        # Flush batch writer to ensure all interactions are persisted
        self._batch_writer.flush()
        # Use cached interactions for incremental metric calculation
        interactions = self._cached_interactions
        
        # Calculate Growth Modifier based on previous metrics and saturation
        latest = getattr(self, "_latest_metrics", {})
        share = latest.get("market_share", 0.1)
        adoption = latest.get("adoption_rate", 0.0)
        modifier = MarketSaturation.calculate_growth_modifier(share, adoption)
        self.simulation.parameters["growth_modifier"] = modifier
        
        metrics = calculate_basic_metrics(self.simulation, interactions, self.tick_count)
        # Apply seasonal multipliers
        seasonal = get_seasonal_multiplier(self.tick_count)
        for key in seasonal:
            if key in metrics:
                metrics[key] = round(metrics[key] * seasonal[key], 4)
        for metric_type, value in metrics.items():
            snapshot = MetricSnapshot(simulation_id=self.simulation.id, timestamp=self.current_time, metric_type=metric_type, value=value)
            self.storage.log_metric(snapshot)
            self.event_bus.publish("metric_changed", {"metric_type": metric_type, "value": value}, self.current_time)
        self._latest_metrics = metrics
    def finalize(self) -> Dict[str, Any]:
        """Generate end-of-simulation critique report."""
        self._batch_writer.flush()
        interactions = self._cached_interactions or self.storage.get_interactions(self.simulation.id)
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

class BatchRunner:
    """Orchestrates multiple simulation runs for experiments."""
    def __init__(self, config: ExperimentConfig, num_runs: int, storage: StorageManager):
        self.config = config
        self.num_runs = num_runs
        self.storage = storage
        
    def run(self):
        """Execute the batch of simulations."""
        base_seed = self.config.seed or random.randint(0, 100000)
        
        for i in range(self.num_runs):
            # Deterministic variation of seed per run
            current_seed = base_seed + i
            logger.info(f"Running batch simulation {i+1}/{self.num_runs} with seed {current_seed}")
            
            # Flatten experiment config into valid simulation parameters
            flat_params = {}
            # Base simulation params
            flat_params.update(asdict(self.config.market_params))
            flat_params.update(asdict(self.config.unit_economics))
            flat_params.update(asdict(self.config.funding_state))
            # Extras
            flat_params["agent_count"] = self.config.agent_count
            flat_params["seed"] = current_seed
            flat_params["experiment_name"] = self.config.simulation_name
            flat_params["batch_run_index"] = i
            
            sim_id = str(uuid.uuid4())
            sim_entity = SimulationEntity(
                id=sim_id,
                name=f"{self.config.simulation_name}_run_{i+1}",
                description=self.config.description,
                industry=self.config.industry,
                stage=self.config.stage,
                parameters=flat_params,
                created_at=time.time()
            )
            
            self.storage.save_simulation(sim_entity)
            
            # Initialize engine with deterministic seed
            engine = SimulationEngine(sim_entity, self.storage, seed=current_seed)
            engine.start() # Set state to running
            
            # Setup LLM with caching for reproducibility
            llm = LLMFactory.create(self.config.llm_model)

            # Wrapper logic for caching if needed (engine handles seed/caching internally via passed params? No, CLI handled it)
            # We must handle it here.
            # If seed set, use cache.
            llm = CachedLLMProvider(llm)
                
            # Populate Agents
            agents = generate_initial_agents(sim_entity)
            
            for agent_entity in agents:
                # Create agent instance
                # Note: GenericAgent uses `world_state` reference.
                agent_impl = GenericAgent(agent_entity, engine.event_bus, llm, engine.world_state)
                engine.register_agent(agent_impl)
                
            # Execution Loop (Headless)
            try:
                # Run max ticks with step
                for tick in range(self.config.duration_ticks):
                    if not engine.is_running:
                        break
                    engine.step()
            except Exception as e:
                logger.error(f"Batch run {i+1} failed: {e}")
            finally:
                engine.stop()
                
            logger.info(f"Batch run {i+1} completed.")
