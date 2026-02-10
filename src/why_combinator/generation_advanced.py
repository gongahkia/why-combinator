"""Advanced procedural generation for rich simulation content."""
import random
import time
from typing import Dict, Any, List
from why_combinator.models import SimulationEntity

def generate_testimonials(simulation: SimulationEntity, count: int = 5) -> List[Dict[str, Any]]:
    """Generate realistic user testimonials and reviews."""
    names = ["Alex M.", "Jordan K.", "Sam R.", "Taylor W.", "Casey P.", "Morgan L.", "Quinn D.", "Riley S."]
    templates = [
        "We switched to {name} {months} months ago and haven't looked back. {detail}",
        "As a {role} at a {size} company, {name} has been {adjective} for our team. {detail}",
        "I was skeptical at first, but {name} {result}. {rating}/5 stars.",
        "The {feature} feature alone is worth the subscription. {name} really understands {industry}.",
    ]
    roles = ["CTO", "product manager", "CEO", "developer", "operations lead"]
    sizes = ["small", "mid-size", "enterprise", "startup", "Fortune 500"]
    adjectives = ["transformative", "essential", "game-changing", "disappointing", "helpful", "revolutionary"]
    details = ["Saved us 20+ hours per week.", "ROI was visible within the first month.", "Still has some rough edges but improving fast.", "Support team is incredibly responsive.", "Integration was seamless."]
    results = []
    for _ in range(count):
        results.append({
            "author": random.choice(names),
            "text": random.choice(templates).format(name=simulation.name, months=random.randint(1, 12), role=random.choice(roles), size=random.choice(sizes), adjective=random.choice(adjectives), detail=random.choice(details), result=random.choice(["exceeded all expectations", "met our needs", "fell short of promises"]), rating=random.randint(2, 5), feature=random.choice(["analytics", "automation", "API", "dashboard", "reporting"]), industry=simulation.industry),
            "rating": random.randint(1, 5),
            "verified": random.random() > 0.3,
        })
    return results

def generate_pitch_deck(simulation: SimulationEntity, metrics: Dict[str, float]) -> Dict[str, Any]:
    """Create procedural pitch deck based on simulation results."""
    return {
        "title": f"{simulation.name} - Series A Pitch",
        "slides": [
            {"title": "The Problem", "content": f"Current solutions in {simulation.industry} are fragmented and inefficient."},
            {"title": "Our Solution", "content": simulation.description},
            {"title": "Market Size", "content": f"TAM: ${random.randint(1, 50)}B | SAM: ${random.randint(100, 999)}M | SOM: ${random.randint(10, 99)}M"},
            {"title": "Traction", "content": f"Adoption rate: {metrics.get('adoption_rate', 0):.1%} | Market share: {metrics.get('market_share', 0):.1%}"},
            {"title": "Business Model", "content": f"MRR target: ${random.randint(10, 500)}K | LTV/CAC: {random.uniform(2, 8):.1f}x"},
            {"title": "Competition", "content": f"Key differentiators in {simulation.industry}: speed, UX, integrations"},
            {"title": "Team", "content": f"Experienced founders with deep {simulation.industry} expertise"},
            {"title": "The Ask", "content": f"Raising ${random.randint(1, 20)}M at ${random.randint(10, 100)}M valuation"},
        ],
    }

def generate_media_articles(simulation: SimulationEntity, count: int = 3) -> List[Dict[str, Any]]:
    """Generate media articles about startup (positive/negative)."""
    positive = [
        f"{simulation.name} Raises New Round, Plans Aggressive {simulation.industry} Expansion",
        f"How {simulation.name} Is Disrupting the {simulation.industry} Industry",
        f"{simulation.name} Named Top 10 Startup to Watch in {simulation.industry}",
        f"Users Love {simulation.name}: Inside the Fastest-Growing {simulation.industry} Platform",
    ]
    negative = [
        f"{simulation.name} Faces Growing Pains as Competition Heats Up",
        f"Is {simulation.name} Overhyped? Industry Experts Weigh In",
        f"{simulation.name} Under Fire for {random.choice(['data practices', 'pricing changes', 'service outages'])}",
        f"Former Employees Speak Out About Culture at {simulation.name}",
    ]
    articles = []
    for _ in range(count):
        is_positive = random.random() > 0.4
        headline = random.choice(positive if is_positive else negative)
        articles.append({"headline": headline, "source": random.choice(["TechCrunch", "The Verge", "Bloomberg", "Wired", "Forbes", "Ars Technica"]), "sentiment": "positive" if is_positive else "negative", "reach": random.randint(1000, 500000)})
    return articles

def generate_term_sheet(simulation: SimulationEntity, round_name: str = "Series A") -> Dict[str, Any]:
    """Build procedural investor term sheets with conditions."""
    valuation = random.randint(5, 100) * 1_000_000
    return {
        "round": round_name, "pre_money_valuation": valuation,
        "investment_amount": int(valuation * random.uniform(0.1, 0.3)),
        "equity_pct": round(random.uniform(10, 30), 1),
        "lead_investor": random.choice(["Sequoia", "a16z", "Accel", "Benchmark", "Founders Fund", "Y Combinator"]),
        "board_seats": random.randint(1, 2),
        "liquidation_preference": f"{random.choice([1, 1.5, 2])}x",
        "anti_dilution": random.choice(["broad-based weighted average", "full ratchet", "narrow-based"]),
        "vesting": "4 years, 1 year cliff",
        "pro_rata_rights": True,
        "conditions": random.sample(["ROFR on secondary sales", "Drag-along rights", "Information rights", "Observer rights", "No-shop clause (30 days)"], k=3),
    }

def generate_social_buzz(simulation: SimulationEntity) -> Dict[str, Any]:
    """Create social media buzz simulation with virality metrics."""
    mentions = random.randint(50, 5000)
    return {
        "total_mentions": mentions,
        "sentiment_breakdown": {"positive": random.uniform(0.3, 0.7), "neutral": random.uniform(0.1, 0.3), "negative": random.uniform(0.05, 0.3)},
        "top_platforms": {"twitter": int(mentions * 0.5), "linkedin": int(mentions * 0.25), "reddit": int(mentions * 0.15), "hackernews": int(mentions * 0.1)},
        "viral_coefficient": random.uniform(0.5, 2.5),
        "trending_topics": [f"#{simulation.name.replace(' ', '')}", f"#{simulation.industry}Tech", "#StartupLife"],
    }

def generate_employee_interviews(simulation: SimulationEntity, count: int = 3) -> List[Dict[str, Any]]:
    """Generate employee interview transcripts."""
    roles = ["Senior Engineer", "Product Designer", "Marketing Lead", "Customer Success Manager", "Data Scientist"]
    sentiments = ["enthusiastic", "cautiously optimistic", "concerned", "neutral"]
    topics = ["culture", "work-life balance", "growth opportunities", "leadership", "compensation", "mission"]
    interviews = []
    for _ in range(count):
        role = random.choice(roles)
        interviews.append({
            "role": role, "tenure_months": random.randint(1, 36),
            "overall_sentiment": random.choice(sentiments),
            "quotes": [
                f"Working at {simulation.name} is {random.choice(['exciting', 'challenging', 'fast-paced', 'intense'])}.",
                f"The {random.choice(topics)} here is {random.choice(['excellent', 'needs work', 'improving', 'unique'])}.",
                f"I {random.choice(['love', 'appreciate', 'struggle with', 'am neutral about'])} the {random.choice(topics)}.",
            ],
            "would_recommend": random.random() > 0.3,
            "glassdoor_rating": round(random.uniform(2.5, 4.8), 1),
        })
    return interviews

def generate_patent_landscape(simulation: SimulationEntity) -> Dict[str, Any]:
    """Build procedural patent/IP landscape analysis."""
    return {
        "total_relevant_patents": random.randint(50, 500),
        "top_holders": [{"name": f"{random.choice(['BigTech', 'IBM', 'Google', 'Amazon', 'Microsoft'])} Corp", "count": random.randint(10, 100)} for _ in range(3)],
        "freedom_to_operate": random.choice(["clear", "some risk", "significant risk"]),
        "recommended_filings": random.randint(1, 5),
        "estimated_cost": f"${random.randint(10, 50)}K per filing",
        "key_risk_areas": random.sample([f"{simulation.industry} core algorithm", "Data processing method", "UI/UX patent", "System architecture", "ML model approach"], k=2),
    }

def generate_competitive_intel(simulation: SimulationEntity) -> Dict[str, Any]:
    """Create competitive intelligence reports."""
    competitors = [f"{random.choice(['Alpha', 'Beta', 'Neo', 'Next', 'Super'])}{random.choice(['Corp', 'ly', 'Hub', 'Labs', 'io'])}" for _ in range(3)]
    return {
        "industry": simulation.industry,
        "competitors": [{
            "name": c,
            "estimated_revenue": f"${random.randint(1, 50)}M ARR",
            "employees": random.randint(10, 500),
            "funding": f"${random.randint(5, 100)}M total",
            "strengths": random.sample(["Brand recognition", "Enterprise relationships", "Technical moat", "Distribution", "Pricing"], k=2),
            "weaknesses": random.sample(["Slow innovation", "Poor UX", "High prices", "Limited market", "Tech debt"], k=2),
        } for c in competitors],
        "market_trends": [f"{simulation.industry} growing at {random.randint(10, 40)}% CAGR", f"Shift toward {random.choice(['AI-first', 'cloud-native', 'mobile-first'])} solutions", f"Consolidation expected in {random.randint(1, 3)} years"],
    }
