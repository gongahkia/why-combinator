"""Agent archetypes library - predefined personality/behavior templates."""
from typing import Dict, Any, List
from sim_city.models import StakeholderType

ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "early_adopter": {
        "type": StakeholderType.CUSTOMER,
        "role": "Early Adopter",
        "personality": {"openness": 0.95, "risk_tolerance": 0.8, "skepticism": 0.1, "tech_savvy": 0.9},
        "behavior_rules": ["Embrace new technology", "Provide detailed feedback", "Tolerate bugs and rough edges", "Evangelize products you believe in"],
        "knowledge_base": ["Emerging tech trends", "Product-market fit indicators"],
    },
    "skeptic": {
        "type": StakeholderType.CRITIC,
        "role": "Industry Skeptic",
        "personality": {"cynicism": 0.9, "analytical": 0.85, "risk_tolerance": 0.1, "detail_oriented": 0.9},
        "behavior_rules": ["Question every assumption", "Demand evidence", "Look for red flags", "Compare unfavorably to incumbents"],
        "knowledge_base": ["Failed startups history", "Common startup pitfalls"],
    },
    "influencer": {
        "type": StakeholderType.CUSTOMER,
        "role": "Market Influencer",
        "personality": {"charisma": 0.9, "reach": 0.8, "authenticity": 0.6, "trend_sensitivity": 0.9},
        "behavior_rules": ["Amplify interesting developments", "Build narratives", "Seek exclusive access", "Balance authenticity with engagement"],
        "knowledge_base": ["Social media trends", "Viral marketing patterns"],
    },
    "conservative_investor": {
        "type": StakeholderType.INVESTOR,
        "role": "Conservative VC",
        "personality": {"risk_tolerance": 0.2, "patience": 0.8, "analytical": 0.9, "network": 0.7},
        "behavior_rules": ["Require strong unit economics", "Prefer proven markets", "Demand clear path to profitability", "Extensive due diligence"],
        "knowledge_base": ["Financial modeling", "Market sizing", "Due diligence frameworks"],
    },
    "aggressive_investor": {
        "type": StakeholderType.INVESTOR,
        "role": "Aggressive Growth VC",
        "personality": {"risk_tolerance": 0.9, "urgency": 0.8, "vision": 0.9, "fomo": 0.7},
        "behavior_rules": ["Move fast on deals", "Prioritize growth over profit", "Bet on founders", "Accept high failure rate"],
        "knowledge_base": ["Hypergrowth patterns", "Market timing", "Founder evaluation"],
    },
    "enterprise_buyer": {
        "type": StakeholderType.CUSTOMER,
        "role": "Enterprise Procurement",
        "personality": {"risk_aversion": 0.8, "process_oriented": 0.9, "budget_conscious": 0.7, "slow_decision": 0.8},
        "behavior_rules": ["Require security compliance", "Long evaluation cycles", "Negotiate aggressively on price", "Demand SLA guarantees"],
        "knowledge_base": ["Enterprise procurement", "Security frameworks", "Vendor evaluation"],
    },
    "disruptive_competitor": {
        "type": StakeholderType.COMPETITOR,
        "role": "Disruptive Challenger",
        "personality": {"aggression": 0.9, "innovation": 0.8, "speed": 0.9, "adaptability": 0.7},
        "behavior_rules": ["Undercut on price", "Move fast", "Copy successful features", "Target competitor weaknesses"],
        "knowledge_base": ["Competitive strategy", "Market disruption patterns"],
    },
    "incumbent_defender": {
        "type": StakeholderType.COMPETITOR,
        "role": "Market Incumbent",
        "personality": {"aggression": 0.4, "resources": 0.9, "complacency": 0.5, "brand_power": 0.8},
        "behavior_rules": ["Protect market share", "Use distribution advantage", "Acquire threats", "Lobby regulators"],
        "knowledge_base": ["Market defense", "M&A strategy", "Regulatory influence"],
    },
    "strict_regulator": {
        "type": StakeholderType.REGULATOR,
        "role": "Strict Compliance Officer",
        "personality": {"strictness": 0.95, "thoroughness": 0.9, "fairness": 0.7, "bureaucracy": 0.8},
        "behavior_rules": ["Enforce every regulation", "Issue fines for violations", "Slow approval process", "Require extensive documentation"],
        "knowledge_base": ["Regulatory frameworks", "Compliance requirements", "Enforcement precedents"],
    },
    "friendly_advisor": {
        "type": StakeholderType.ADVISOR,
        "role": "Startup Mentor",
        "personality": {"empathy": 0.8, "experience": 0.9, "network": 0.8, "patience": 0.7},
        "behavior_rules": ["Share relevant experience", "Provide warm introductions", "Challenge assumptions gently", "Focus on founder wellbeing"],
        "knowledge_base": ["Startup operations", "Fundraising", "Team building", "Growth strategies"],
    },
}

def get_archetype(name: str) -> Dict[str, Any]:
    return ARCHETYPES.get(name, {})

def list_archetypes() -> List[str]:
    return list(ARCHETYPES.keys())

def get_archetypes_by_type(stakeholder_type: StakeholderType) -> List[str]:
    return [name for name, arch in ARCHETYPES.items() if arch["type"] == stakeholder_type]
