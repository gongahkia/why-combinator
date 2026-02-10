"""Procedural data generation for simulation outputs."""
import random
import time
from typing import Dict, Any, List
from why_combinator.models import SimulationEntity, MetricSnapshot, InteractionLog

CUSTOMER_FEEDBACK_TEMPLATES = [
    "I {feeling} this product. {reason}",
    "As a {segment} user, I find {product} to be {adjective}. {detail}",
    "{product} {verb} my expectations. {recommendation}",
]
FEELINGS = ["love", "like", "am skeptical about", "dislike", "am neutral about"]
REASONS = [
    "It solves a real problem.", "The UX needs work.", "Pricing feels right.",
    "Too many competitors do this better.", "This is a game-changer for the industry.",
    "I'd recommend it to friends.", "Not sure about long-term viability.",
]
SEGMENTS = ["early adopter", "mainstream", "enterprise", "budget-conscious", "tech-savvy"]
ADJECTIVES = ["innovative", "overpriced", "promising", "confusing", "essential", "redundant"]

COMPETITOR_MOVES = [
    "Launched a competing feature targeting {industry} segment.",
    "Lowered prices by {pct}% to capture market share.",
    "Acquired a smaller player in the {industry} space.",
    "Announced partnership with major enterprise client.",
    "Released negative press about new entrants.",
    "Pivoted strategy to focus on {industry} vertical.",
    "Increased marketing spend significantly.",
]

INVESTOR_QUESTIONS = [
    "What's your CAC and LTV ratio?",
    "How do you plan to reach profitability?",
    "Who are your top 3 competitors and what's your moat?",
    "What's your runway at current burn rate?",
    "How does your team handle technical debt?",
    "What's your growth rate month-over-month?",
    "Why hasn't this been done before?",
    "What regulatory risks do you face in {industry}?",
]

REGULATORY_CONCERNS = {
    "fintech": ["KYC/AML compliance", "banking license requirements", "data protection (GDPR/CCPA)", "cross-border payment regulations"],
    "health": ["FDA approval process", "HIPAA compliance", "clinical trial requirements", "medical device regulations"],
    "ai": ["algorithmic bias regulations", "AI transparency requirements", "data privacy concerns", "intellectual property issues"],
    "saas": ["data residency requirements", "SOC 2 compliance", "GDPR data processing", "terms of service regulations"],
    "default": ["general data protection", "consumer protection laws", "industry licensing", "tax compliance"],
}

def generate_customer_feedback(simulation: SimulationEntity, count: int = 5) -> List[Dict[str, Any]]:
    """Generate procedural customer feedback based on product description."""
    feedbacks = []
    for _ in range(count):
        template = random.choice(CUSTOMER_FEEDBACK_TEMPLATES)
        feedback = template.format(
            feeling=random.choice(FEELINGS),
            reason=random.choice(REASONS),
            segment=random.choice(SEGMENTS),
            product=simulation.name,
            adjective=random.choice(ADJECTIVES),
            detail=random.choice(REASONS),
            verb=random.choice(["exceeded", "met", "fell short of"]),
            recommendation=random.choice(["Would recommend.", "Needs improvement.", "Wait and see."]),
        )
        feedbacks.append({"type": "customer_feedback", "content": feedback, "sentiment": random.uniform(-1, 1), "timestamp": time.time()})
    return feedbacks

def generate_competitor_moves(simulation: SimulationEntity, count: int = 3) -> List[Dict[str, Any]]:
    """Generate competitor market moves based on industry dynamics."""
    moves = []
    for _ in range(count):
        template = random.choice(COMPETITOR_MOVES)
        move = template.format(industry=simulation.industry, pct=random.randint(5, 30))
        moves.append({"type": "competitor_move", "content": move, "impact": random.uniform(-0.5, 0.5), "timestamp": time.time()})
    return moves

def generate_investor_questions(simulation: SimulationEntity, count: int = 4) -> List[Dict[str, Any]]:
    """Generate investor questions and concerns based on business model."""
    questions = random.sample(INVESTOR_QUESTIONS, min(count, len(INVESTOR_QUESTIONS)))
    return [{"type": "investor_question", "content": q.format(industry=simulation.industry), "urgency": random.uniform(0, 1), "timestamp": time.time()} for q in questions]

def generate_regulatory_considerations(simulation: SimulationEntity) -> List[Dict[str, Any]]:
    """Generate regulatory considerations based on industry type."""
    industry_lower = simulation.industry.lower()
    concerns = REGULATORY_CONCERNS.get("default", [])
    for key in REGULATORY_CONCERNS:
        if key in industry_lower:
            concerns = REGULATORY_CONCERNS[key]
            break
    return [{"type": "regulatory_concern", "content": c, "severity": random.choice(["low", "medium", "high"]), "timestamp": time.time()} for c in concerns]

def generate_critique_report(simulation: SimulationEntity, interactions: List[InteractionLog], metrics: Dict[str, float]) -> Dict[str, Any]:
    """Create critique report at simulation end summarizing insights."""
    total_actions = len(interactions)
    action_counts: Dict[str, int] = {}
    for log in interactions:
        action_counts[log.action] = action_counts.get(log.action, 0) + 1
    top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    strengths, weaknesses = [], []
    if metrics.get("adoption_rate", 0) > 0.3:
        strengths.append("Strong early adoption signals")
    else:
        weaknesses.append("Low adoption rate - product-market fit unclear")
    if metrics.get("churn_rate", 1) < 0.1:
        strengths.append("Low churn indicates sticky product")
    else:
        weaknesses.append("High churn rate needs addressing")
    if metrics.get("market_share", 0) > 0.05:
        strengths.append("Meaningful market share captured")
    else:
        weaknesses.append("Minimal market penetration")
    if metrics.get("burn_rate", 0) < 50000:
        strengths.append("Efficient burn rate")
    else:
        weaknesses.append("Burn rate may be unsustainable")
    return {
        "simulation": simulation.name,
        "industry": simulation.industry,
        "stage": simulation.stage.value,
        "total_interactions": total_actions,
        "top_actions": top_actions,
        "metrics_summary": metrics,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendation": "Proceed with caution" if len(weaknesses) > len(strengths) else "Promising trajectory",
    }

def calculate_basic_metrics(simulation: SimulationEntity, interactions: List[InteractionLog], tick_count: int) -> Dict[str, float]:
    """Calculate metrics derived from agent behavior."""
    positive_actions = {"buy", "invest", "partner", "collaborate"}
    negative_actions = {"complain", "sell", "criticize", "ignore"}
    total_agents = max(len(set(i.agent_id for i in interactions)), 1)
    total = len(interactions) or 1

    # Adoption: cumulative positive actions relative to total agents and ticks
    positive_count = sum(1 for i in interactions if i.action in positive_actions)
    adoption_rate = min(positive_count / (total_agents * max(tick_count, 1)) * 5, 1.0)

    # Churn: agents who previously did positive actions but switched to negative
    agent_actions: Dict[str, List[str]] = {}
    for i in interactions:
        agent_actions.setdefault(i.agent_id, []).append(i.action)
    churned = 0
    for aid, actions in agent_actions.items():
        had_positive = any(a in positive_actions for a in actions[:-3] if len(actions) > 3)
        recent_negative = any(a in negative_actions for a in actions[-3:]) if len(actions) >= 3 else False
        if had_positive and recent_negative:
            churned += 1
    churn_rate = churned / total_agents

    # Market share: from competitive market results if available, else behavioral
    market_share = min(positive_count / (total * 2), 0.5)

    # Burn rate: influenced by employee actions and stage
    stage_burn = {"idea": 10000, "mvp": 30000, "launch": 60000, "growth": 100000, "scale": 200000}
    base_burn = stage_burn.get(simulation.stage.value, 50000)
    employee_actions = [i for i in interactions if i.action in ("complain", "wait") and "employee" in str(i.outcome).lower()]
    morale_factor = 1.0 + len(employee_actions) * 0.01  # low morale increases burn
    burn_rate = base_burn * morale_factor

    # Revenue: buy-action count * price-per-unit
    price_per_unit = simulation.parameters.get("price_per_unit", 100.0)
    buy_count = sum(1 for i in interactions if i.action == "buy")
    revenue = buy_count * price_per_unit

    # Runway: (initial_capital - cumulative_burn) / monthly_burn_rate
    initial_capital = simulation.parameters.get("initial_capital", 500000)
    months_elapsed = max(tick_count / 30, 1)  # ~30 ticks per month
    cumulative_burn = burn_rate * months_elapsed
    monthly_burn = burn_rate if burn_rate > 0 else 1
    runway_months = max((initial_capital - cumulative_burn) / monthly_burn, 0)

    return {
        "adoption_rate": round(adoption_rate, 4),
        "churn_rate": round(churn_rate, 4),
        "market_share": round(market_share, 4),
        "burn_rate": round(burn_rate, 2),
        "revenue": round(revenue, 2),
        "runway_months": round(runway_months, 1),
    }
