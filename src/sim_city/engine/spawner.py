from typing import List, Dict, Any
import uuid

from sim_city.models import SimulationEntity, AgentEntity, StakeholderType, SimulationStage


def generate_initial_agents(simulation: SimulationEntity) -> List[AgentEntity]:
    """
    Generate the initial set of agents based on simulation parameters.
    """
    agents = []

    # 1. Core Customer (The Market)
    agents.append(create_agent(
        type=StakeholderType.CUSTOMER,
        role="Early Adopter",
        simulation=simulation,
        personality={"openness": 0.9, "skepticism": 0.2},
        behavior_rules=["Evaluate product based on innovation", "Provide honest feedback"]
    ))

    # 2. Competitor (The Rival)
    agents.append(create_agent(
        type=StakeholderType.COMPETITOR,
        role="Incumbent",
        simulation=simulation,
        personality={"aggression": 0.6, "adaptability": 0.3},
        behavior_rules=["Monitor market for new entrants", "Protect market share"]
    ))

    # 3. Investor (The Money)
    if simulation.stage in [SimulationStage.MVP, SimulationStage.LAUNCH, SimulationStage.GROWTH]:
        role = "Angel Investor" if simulation.stage == SimulationStage.MVP else "VC Partner"
        agents.append(create_agent(
            type=StakeholderType.INVESTOR,
            role=role,
            simulation=simulation,
            personality={"risk_tolerance": 0.7 if simulation.stage == SimulationStage.MVP else 0.4},
            behavior_rules=["Seek high ROI", "Evaluate team and traction"]
        ))

    # 4. Regulator (The Law)
    industry_lower = simulation.industry.lower()
    regulator_name = "Generic Regulator"
    if "fintech" in industry_lower or "finance" in industry_lower:
        regulator_name = "Financial Authority (SEC/FCA)"
    elif "health" in industry_lower or "bio" in industry_lower:
        regulator_name = "Health Authority (FDA)"
    
    agents.append(create_agent(
        type=StakeholderType.REGULATOR,
        role=regulator_name,
        simulation=simulation,
        personality={"strictness": 0.8},
        behavior_rules=["Enforce compliance", "Monitor for violations"]
    ))

    # 5. Critic (The Hater/Skeptic)
    agents.append(create_agent(
        type=StakeholderType.CRITIC,
        role="Tech Blogger",
        simulation=simulation,
        personality={"cynicism": 0.8, "detail_oriented": 0.9},
        behavior_rules=["Find flaws", "Question viability"]
    ))

    return agents


def create_agent(type: StakeholderType, role: str, simulation: SimulationEntity, personality: Dict[str, Any], behavior_rules: List[str]) -> AgentEntity:
    return AgentEntity(
        id=str(uuid.uuid4()),
        type=type,
        role=role,
        personality=personality,
        knowledge_base=[f"Knowledge about {simulation.industry}", f"Expertise in {role}"],
        behavior_rules=behavior_rules,
        name=f"{role} ({type.value.title()})"
    )
