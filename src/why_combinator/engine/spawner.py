from typing import List, Dict, Any
import uuid
from why_combinator.models import SimulationEntity, AgentEntity, StakeholderType, SimulationStage

def generate_initial_agents(simulation: SimulationEntity) -> List[AgentEntity]:
    """Generate the initial set of agents based on simulation parameters."""
    agents = []
    agents.append(create_agent(type=StakeholderType.CUSTOMER, role="Early Adopter", simulation=simulation, personality={"openness": 0.9, "skepticism": 0.2, "segment": "early_adopter"}, behavior_rules=["Evaluate product based on innovation", "Provide honest feedback"]))
    agents.append(create_agent(type=StakeholderType.CUSTOMER, role="Mainstream User", simulation=simulation, personality={"openness": 0.4, "skepticism": 0.6, "segment": "mainstream"}, behavior_rules=["Require proven value", "Price sensitive", "Compare alternatives"]))
    agents.append(create_agent(type=StakeholderType.CUSTOMER, role="Late Majority", simulation=simulation, personality={"openness": 0.2, "skepticism": 0.8, "segment": "laggard"}, behavior_rules=["Resist change", "Only adopt when necessary", "Demand simplicity"]))
    agents.append(create_agent(type=StakeholderType.COMPETITOR, role="Incumbent", simulation=simulation, personality={"aggression": 0.6, "adaptability": 0.3}, behavior_rules=["Monitor market for new entrants", "Protect market share"]))
    if simulation.stage in [SimulationStage.MVP, SimulationStage.LAUNCH, SimulationStage.GROWTH]:
        role = "Angel Investor" if simulation.stage == SimulationStage.MVP else "VC Partner"
        agents.append(create_agent(type=StakeholderType.INVESTOR, role=role, simulation=simulation, personality={"risk_tolerance": 0.7 if simulation.stage == SimulationStage.MVP else 0.4}, behavior_rules=["Seek high ROI", "Evaluate team and traction"]))
    industry_lower = simulation.industry.lower()
    regulator_name = "Generic Regulator"
    if "fintech" in industry_lower or "finance" in industry_lower:
        regulator_name = "Financial Authority (SEC/FCA)"
    elif "health" in industry_lower or "bio" in industry_lower:
        regulator_name = "Health Authority (FDA)"
    elif "ai" in industry_lower:
        regulator_name = "AI Safety Board"
    elif "crypto" in industry_lower or "blockchain" in industry_lower:
        regulator_name = "Securities Regulator (SEC)"
    elif "food" in industry_lower:
        regulator_name = "Food Safety Authority (FDA)"
    elif "education" in industry_lower or "edtech" in industry_lower:
        regulator_name = "Education Standards Board"
    agents.append(create_agent(type=StakeholderType.REGULATOR, role=regulator_name, simulation=simulation, personality={"strictness": 0.8}, behavior_rules=["Enforce compliance", "Monitor for violations"]))
    agents.append(create_agent(type=StakeholderType.CRITIC, role="Tech Blogger", simulation=simulation, personality={"cynicism": 0.8, "detail_oriented": 0.9}, behavior_rules=["Find flaws", "Question viability"]))
    agents.append(create_agent(type=StakeholderType.EMPLOYEE, role="Lead Engineer", simulation=simulation, personality={"morale": 0.7, "productivity": 0.8, "loyalty": 0.6}, behavior_rules=["Build the product", "Flag technical debt", "Consider work-life balance"]))
    agents.append(create_agent(type=StakeholderType.PARTNER, role="Integration Partner", simulation=simulation, personality={"collaboration": 0.7, "mutual_benefit": 0.8}, behavior_rules=["Seek synergies", "Protect own interests", "Evaluate integration effort"]))
    agents.append(create_agent(type=StakeholderType.MEDIA, role="Tech Journalist", simulation=simulation, personality={"curiosity": 0.8, "reach": 0.7, "sensationalism": 0.4}, behavior_rules=["Cover newsworthy developments", "Seek exclusive stories", "Balance objectivity"]))
    agents.append(create_agent(type=StakeholderType.SUPPLIER, role="Cloud Provider", simulation=simulation, personality={"reliability": 0.9, "pricing_flexibility": 0.3}, behavior_rules=["Negotiate contracts", "Ensure SLA compliance", "Upsell services"]))
    agents.append(create_agent(type=StakeholderType.ADVISOR, role="Startup Mentor", simulation=simulation, personality={"experience": 0.9, "empathy": 0.7, "network": 0.8}, behavior_rules=["Share relevant experience", "Provide warm intros", "Challenge assumptions gently"]))
    return agents

def create_agent(type: StakeholderType, role: str, simulation: SimulationEntity, personality: Dict[str, Any], behavior_rules: List[str]) -> AgentEntity:
    return AgentEntity(
        id=str(uuid.uuid4()), type=type, role=role, personality=personality,
        knowledge_base=[f"Knowledge about {simulation.industry}", f"Expertise in {role}"],
        behavior_rules=behavior_rules, name=f"{role} ({type.value.title()})"
    )
