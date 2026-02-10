"""Procedural data generation for simulation outputs."""
import random
import math
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

    # Adoption: Logistic S-Curve model
    # Model: P(t) = 1 / (1 + exp(-k * (t - t0)))
    params = simulation.parameters
    viral_coeff = params.get("viral_coefficient", 0.1)
    conv_rate = params.get("conversion_rate", 0.05)
    
    # k denotes the growth rate (steepness)
    # We combine viral coefficient and conversion rate to derive k
    k = (viral_coeff * 0.5) + (conv_rate * 2.0)
    
    # t0 is the inflection point (ticks to 50% adoption)
    t0 = params.get("inflection_tick", 100)
    
    try:
        adoption_rate = 1.0 / (1.0 + math.exp(-k * (tick_count - t0)))
    except OverflowError:
        # constant high or low
        adoption_rate = 0.0 if (tick_count - t0) < 0 else 1.0

    # Churn: Cohort-based retention decay
    # Model: Survival(t) = 0.5 ^ (t / half_life)
    # Churn Rate = 1 - (Active / Total)
    
    retention_half_life = params.get("retention_half_life", 200.0)
    
    if not interactions:
        churn_rate = 0.0
    else:
        # Determine time scale
        start_time = interactions[0].timestamp
        end_time = interactions[-1].timestamp
        duration = end_time - start_time
        if duration <= 0:
            ticks_per_sec = 1.0
        else:
            ticks_per_sec = tick_count / duration
            
        agent_start_times = {}
        for i in interactions:
            if i.agent_id not in agent_start_times:
                agent_start_times[i.agent_id] = i.timestamp
                
        expected_active_sum = 0.0
        current_time_ref = end_time
        
        for aid, start_ts in agent_start_times.items():
            age_seconds = current_time_ref - start_ts
            age_ticks = age_seconds * ticks_per_sec
            survival_prob = 0.5 ** (age_ticks / retention_half_life)
            expected_active_sum += survival_prob
            
        churn_rate = 1.0 - (expected_active_sum / len(agent_start_times)) if agent_start_times else 0.0

    # Market share: Relative Product Quality vs Competitors
    # Share = Q_me / (Q_me + Sum(Q_comp))
    
    # Calculate My Quality Score based on interaction sentiment proxy
    # We define quality as ratio of positive to negative interactions
    positive_interactions = sum(1 for i in interactions if i.action in positive_actions)
    negative_interactions = sum(1 for i in interactions if i.action in negative_actions)
    total_relevant = positive_interactions + negative_interactions
    
    if total_relevant > 0:
        my_quality_score = positive_interactions / total_relevant
    else:
        my_quality_score = 0.5 # Neutral baseline
        
    # Competitor parameters
    competitor_count = params.get("competitor_count", 3)
    competitor_quality_avg = params.get("competitor_quality_avg", 0.5)
    
    # Market Share formula
    if competitor_count == 0:
         market_share = my_quality_score # Monopoly modulated by quality?? Or 1.0?
         # If monopoly, share is 1.0 of the addressable market captured so far?
         # But "Market Share" usually implies relative to competition.
         # We'll use 1.0 if no competitors, but usually market share <= 1.0
         market_share = 1.0
    else:
         total_quality_pool = my_quality_score + (competitor_count * competitor_quality_avg)
         market_share = my_quality_score / total_quality_pool if total_quality_pool > 0 else 0.0

    # Revenue: buy-action count in last 30 ticks * price-per-unit
    price_per_unit = simulation.parameters.get("price_per_unit", 100.0)
    month_window = 30
    
    # Calculate Monthly Metrics (implied last 30 ticks)
    # We use a simple average rate based on total tick count due to lack of tick history in InteractionLog
    buy_count_total = sum(1 for i in interactions if i.action == "buy")
    monthly_revenue = (buy_count_total / max(tick_count, 1)) * 30 * price_per_unit
    monthly_new_customers = (buy_count_total / max(tick_count, 1)) * 30
    
    # Burn Rate Calculation (Unit Economics)
    params = simulation.parameters
    cac = params.get("cac", 50.0)
    gross_margin = params.get("gross_margin", 0.7)
    opex_ratio = params.get("opex_ratio", 0.5) # Opex as % of Revenue
    base_opex = params.get("base_opex", 5000.0) # Fixed monthly cost
    
    cogs = monthly_revenue * (1 - gross_margin)
    marketing_spend = monthly_new_customers * cac
    variable_opex = monthly_revenue * opex_ratio
    
    burn_rate = base_opex + cogs + marketing_spend + variable_opex
    
    # Adjust for morale
    employee_actions = [i for i in interactions if i.action in ("complain", "wait") and "employee" in str(i.outcome).lower()]
    morale_factor = 1.0 + len(employee_actions) * 0.001 
    burn_rate *= morale_factor

    revenue = buy_count_total * price_per_unit
    
    # Runway calculation
    initial_capital = params.get("initial_capital", 500000)
    months_elapsed = max(tick_count / 30, 1)
    # Approximate cumulative burn
    cumulative_burn = burn_rate * months_elapsed
    
    monthly_burn = burn_rate if burn_rate > 0 else 1
    runway_months = max((initial_capital - cumulative_burn + revenue) / monthly_burn, 0)

    return {
        "adoption_rate": round(adoption_rate, 4),
        "churn_rate": round(churn_rate, 4),
        "market_share": round(market_share, 4),
        "burn_rate": round(burn_rate, 2),
        "revenue": round(revenue, 2),
        "runway_months": round(runway_months, 1),
    }
