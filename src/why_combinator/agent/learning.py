"""Agent learning system - extract lessons from past simulation runs."""
import logging
from typing import List, Dict, Any
from why_combinator.storage import StorageManager
from why_combinator.models import InteractionLog

logger = logging.getLogger(__name__)

def extract_lessons(storage: StorageManager, simulation_id: str, agent_id: str, max_lessons: int = 10) -> List[str]:
    """Extract learning lessons from past interactions for an agent."""
    interactions = storage.get_interactions(simulation_id)
    agent_interactions = [i for i in interactions if i.agent_id == agent_id]
    if not agent_interactions:
        return []
    action_outcomes: Dict[str, List[str]] = {}
    for inter in agent_interactions:
        action_outcomes.setdefault(inter.action, []).append(str(inter.outcome))
    lessons = []
    for action, outcomes in action_outcomes.items():
        count = len(outcomes)
        if count >= 2:
            lessons.append(f"Action '{action}' was taken {count} times. Common pattern: {outcomes[-1][:80]}")
    return lessons[:max_lessons]

def load_cross_simulation_lessons(storage: StorageManager, agent_type: str) -> List[str]:
    """Load lessons from ALL past simulations for a given agent type."""
    lessons = []
    for sim in storage.list_simulations():
        agents = storage.get_agents(sim.id)
        for agent in agents:
            if agent.type.value == agent_type:
                sim_lessons = extract_lessons(storage, sim.id, agent.id, max_lessons=3)
                for l in sim_lessons:
                    lessons.append(f"[{sim.name}] {l}")
    return lessons[:20] # cap at 20

def inject_lessons_into_agent(agent, storage: StorageManager, simulation_id: str):
    """Inject past lessons into agent memory before simulation starts."""
    own_lessons = extract_lessons(storage, simulation_id, agent.entity.id)
    cross_lessons = load_cross_simulation_lessons(storage, agent.entity.type.value)
    for lesson in own_lessons:
        agent.add_memory(f"Past lesson: {lesson}", role="learning")
    for lesson in cross_lessons[:5]: # top 5 cross-sim lessons
        agent.add_memory(f"Cross-sim insight: {lesson}", role="learning")
    if own_lessons or cross_lessons:
        logger.info(f"Injected {len(own_lessons)} own + {min(len(cross_lessons), 5)} cross-sim lessons into {agent.entity.name}")
