"""Complex simulation scenarios: multi-phase, crisis, competitive, macro events."""
import random
import logging
from typing import List, Dict, Any, Optional
from why_combinator.models import SimulationEntity, SimulationStage
from why_combinator.events import EventBus

logger = logging.getLogger(__name__)

PHASES = [SimulationStage.IDEA, SimulationStage.MVP, SimulationStage.LAUNCH, SimulationStage.GROWTH, SimulationStage.SCALE]
PHASE_THRESHOLDS = {SimulationStage.IDEA: 20, SimulationStage.MVP: 50, SimulationStage.LAUNCH: 100, SimulationStage.GROWTH: 200, SimulationStage.SCALE: 500}

class MultiPhaseManager:
    """Manages phase transitions: idea -> MVP -> launch -> growth -> scale."""
    def __init__(self, simulation: SimulationEntity, event_bus: EventBus):
        self.simulation = simulation
        self.event_bus = event_bus
        self.current_phase_idx = PHASES.index(simulation.stage) if simulation.stage in PHASES else 0
    def check_transition(self, tick: int, metrics: Dict[str, float]) -> bool:
        if self.current_phase_idx >= len(PHASES) - 1:
            return False
        current_phase = PHASES[self.current_phase_idx]
        threshold = PHASE_THRESHOLDS.get(current_phase, 100)
        adoption = metrics.get("adoption_rate", 0)
        if tick >= threshold and adoption > 0.1 * (self.current_phase_idx + 1):
            self.current_phase_idx += 1
            new_phase = PHASES[self.current_phase_idx]
            self.simulation.stage = new_phase
            self.event_bus.publish("phase_transition", {"from": current_phase.value, "to": new_phase.value, "tick": tick}, 0)
            logger.info(f"Phase transition: {current_phase.value} -> {new_phase.value}")
            return True
        return False

CRISIS_TYPES = [
    {"name": "PR Disaster", "description": "Major negative press coverage goes viral", "impact": {"adoption_rate": -0.15, "market_share": -0.05}},
    {"name": "Funding Gap", "description": "Key funding round falls through", "impact": {"burn_rate": 1.5}},
    {"name": "Key Employee Loss", "description": "CTO/key engineer leaves for competitor", "impact": {"adoption_rate": -0.05}},
    {"name": "Security Breach", "description": "Customer data exposed in security incident", "impact": {"adoption_rate": -0.2, "churn_rate": 0.1}},
    {"name": "Regulatory Action", "description": "Regulator issues cease-and-desist", "impact": {"market_share": -0.1}},
]

MACRO_EVENTS = [
    {"name": "Economic Recession", "description": "Broad economic downturn reduces spending", "impact": {"adoption_rate": -0.1, "burn_rate": 0.8}},
    {"name": "Economic Boom", "description": "Strong economy increases investment", "impact": {"adoption_rate": 0.1, "market_share": 0.05}},
    {"name": "Policy Change", "description": "New regulation affects industry", "impact": {"churn_rate": 0.05}},
    {"name": "Interest Rate Hike", "description": "Higher rates reduce VC activity", "impact": {"burn_rate": 1.2}},
]

DISRUPTION_EVENTS = [
    {"name": "New Platform Launch", "description": "Major tech company launches competing platform", "impact": {"market_share": -0.15}},
    {"name": "Technology Obsolescence", "description": "Core technology becomes outdated", "impact": {"adoption_rate": -0.2}},
    {"name": "AI Breakthrough", "description": "New AI capability disrupts market", "impact": {"adoption_rate": 0.1}},
]

SEASONAL_PATTERNS = {
    "q1": {"adoption_rate": 0.9, "burn_rate": 1.0}, # post-holiday slowdown
    "q2": {"adoption_rate": 1.1, "burn_rate": 1.0}, # spring growth
    "q3": {"adoption_rate": 0.95, "burn_rate": 0.9}, # summer lull
    "q4": {"adoption_rate": 1.2, "burn_rate": 1.1}, # year-end push
}

class EventGenerator:
    """Generates random events during simulation."""
    def __init__(self, event_bus: EventBus, crisis_probability: float = 0.02, macro_probability: float = 0.01, disruption_probability: float = 0.005):
        self.event_bus = event_bus
        self.crisis_prob = crisis_probability
        self.macro_prob = macro_probability
        self.disruption_prob = disruption_probability
    def maybe_trigger(self, tick: int) -> Optional[Dict[str, Any]]:
        """Roll for random events each tick."""
        if random.random() < self.crisis_prob:
            crisis = random.choice(CRISIS_TYPES)
            self.event_bus.publish("crisis", {"tick": tick, **crisis}, 0)
            logger.warning(f"Crisis triggered: {crisis['name']}")
            return crisis
        if random.random() < self.macro_prob:
            macro = random.choice(MACRO_EVENTS)
            self.event_bus.publish("macro_event", {"tick": tick, **macro}, 0)
            logger.info(f"Macro event: {macro['name']}")
            return macro
        if random.random() < self.disruption_prob:
            disruption = random.choice(DISRUPTION_EVENTS)
            self.event_bus.publish("disruption", {"tick": tick, **disruption}, 0)
            logger.info(f"Disruption: {disruption['name']}")
            return disruption
        return None

def get_seasonal_multiplier(tick: int) -> Dict[str, float]:
    """Get seasonal multiplier based on tick (assume ~90 ticks per quarter)."""
    quarter = (tick // 90) % 4
    quarters = ["q1", "q2", "q3", "q4"]
    return SEASONAL_PATTERNS.get(quarters[quarter], {"adoption_rate": 1.0, "burn_rate": 1.0})

class CompetitiveMarket:
    """Simulates competitive dynamics with multiple competitors."""
    def __init__(self, num_competitors: int = 3):
        self.competitors = [{"name": f"Competitor-{i+1}", "market_share": random.uniform(0.1, 0.3), "aggression": random.uniform(0.3, 0.9)} for i in range(num_competitors)]
    def simulate_step(self, our_share: float) -> Dict[str, Any]:
        total_competitor_share = sum(c["market_share"] for c in self.competitors)
        for c in self.competitors:
            if random.random() < c["aggression"] * 0.1:
                steal = min(our_share * 0.02, 0.01)
                c["market_share"] += steal
                our_share = max(0, our_share - steal)
        return {"our_share": our_share, "competitors": [{"name": c["name"], "share": c["market_share"]} for c in self.competitors]}

class MergerAcquisition:
    """M&A simulation capabilities."""
    def __init__(self):
        self.offers: List[Dict[str, Any]] = []
    def generate_offer(self, simulation: SimulationEntity, metrics: Dict[str, float]) -> Dict[str, Any]:
        valuation = metrics.get("adoption_rate", 0) * metrics.get("market_share", 0) * 100_000_000
        offer = {"type": random.choice(["acquisition", "merger", "acqui-hire"]), "valuation": valuation * random.uniform(0.8, 2.5), "acquirer": f"{random.choice(['BigCorp', 'TechGiant', 'PrivateEquity'])} Partners", "conditions": random.sample(["retain team 2yr", "non-compete 3yr", "earnout based", "cash + stock", "IP transfer"], k=2)}
        self.offers.append(offer)
        return offer

class PivotScenario:
    """Simulate startup pivots with reputational consequences."""
    def __init__(self):
        self.pivot_count = 0
    def pivot(self, new_description: str, simulation: SimulationEntity) -> Dict[str, Any]:
        self.pivot_count += 1
        reputation_hit = min(self.pivot_count * 0.1, 0.5) # each pivot costs more reputation
        simulation.description = new_description
        return {"pivot_number": self.pivot_count, "reputation_cost": reputation_hit, "new_direction": new_description}

class MarketSaturation:
    """Models the dampening effect of market saturation on growth."""
    @staticmethod
    def calculate_growth_modifier(market_share: float, penetration: float) -> float:
        """
        Calculate growth modifier (0.0 - 1.0).
        As market_share approaches 1.0 (monopoly) or penetration approaches 1.0 (fully saturated),
        growth becomes harder.
        """
        # Saturation penalty
        saturation_penalty = 1.0
        if penetration > 0.8:
            saturation_penalty = max(0.0, 1.0 - (penetration - 0.8) * 2.0) # 0.8->1.0, 1.0->0.6
            
        # Dominance penalty (harder to grow when you afford everyone)
        dominance_penalty = 1.0
        if market_share > 0.7:
             dominance_penalty = max(0.0, 1.0 - (market_share - 0.7)) # 0.7->1.0, 1.0->0.7
             
        return min(saturation_penalty, dominance_penalty)
