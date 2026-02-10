"""Procedural data generation for simulation outputs."""
import random
import math
import time
from typing import Dict, Any, List
from why_combinator.models import SimulationEntity, MetricSnapshot, InteractionLog
from why_combinator.economics import (
    calculate_adoption_rate, calculate_churn_rate, calculate_market_share,
    calculate_revenue_metrics, calculate_burn_rate, calculate_runway,
    calculate_product_quality,
    MarketParams, UnitEconomics, FundingState
)

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
    params = simulation.parameters
    
    # 1. Adoption Rate
    market_params = MarketParams(
        tam=float(params.get("tam", 10000.0)),
        viral_coefficient=float(params.get("viral_coefficient", 0.1)),
        conversion_rate=float(params.get("conversion_rate", 0.05)),
        competitor_count=int(params.get("competitor_count", 3)),
        competitor_quality_avg=float(params.get("competitor_quality_avg", 0.5)),
        retention_half_life=float(params.get("retention_half_life", 200.0)),
        inflection_tick=int(params.get("inflection_tick", 100))
    )
    
    adoption_rate = calculate_adoption_rate(market_params, tick_count)
    
    # 2. Churn Rate
    churn_rate = calculate_churn_rate(interactions, tick_count, market_params.retention_half_life)
    
    # 3. Market Share
    market_share = calculate_market_share(interactions, market_params)
    product_quality = calculate_product_quality(interactions)
    
    # 4. Revenue Metrics
    price_per_unit = float(params.get("price_per_unit", 100.0))
    revenue_model = str(params.get("revenue_model", "transactional"))
    
    revenue_metrics = calculate_revenue_metrics(interactions, tick_count, price_per_unit, revenue_model)
    monthly_revenue = revenue_metrics["monthly_revenue"]
    cumulative_revenue = revenue_metrics["cumulative_revenue"]
    monthly_new_customers = revenue_metrics["monthly_new_customers"]
    
    # 5. Burn Rate
    unit_econ = UnitEconomics(
        cac=float(params.get("cac", 50.0)),
        gross_margin=float(params.get("gross_margin", 0.7)),
        opex_ratio=float(params.get("opex_ratio", 0.5)),
        base_opex=float(params.get("base_opex", 5000.0)),
        price_per_unit=price_per_unit
    )
    
    burn_rate = calculate_burn_rate(unit_econ, monthly_revenue, monthly_new_customers, interactions)
    
    # 6. Runway
    funding = FundingState(
        initial_capital=float(params.get("initial_capital", 500000)),
        revenue_growth_rate=float(params.get("revenue_growth_rate", 0.05)),
        burn_growth_rate=float(params.get("burn_growth_rate", 0.02))
    )
    
    months_elapsed = max(tick_count / 30, 1)
    cumulative_burn_approx = burn_rate * months_elapsed
    
    runway_months = calculate_runway(
        funding, burn_rate, monthly_revenue, 
        cumulative_burn_approx, cumulative_revenue, tick_count
    )
    
    return {
        "adoption_rate": round(adoption_rate, 4),
        "churn_rate": round(churn_rate, 4),
        "market_share": round(market_share, 4),
        "product_quality": round(product_quality, 4),
        "burn_rate": round(burn_rate, 2),
        "revenue": round(cumulative_revenue, 2),
        "runway_months": round(runway_months, 1),
    }
