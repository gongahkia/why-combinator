from typing import List, Dict, Any, Optional
import json
import random
import re
from why_combinator.llm.base import LLMProvider

# Personality-weighted action probabilities per agent type
AGENT_TYPE_ACTIONS = {
    "customer": {"buy": 0.30, "complain": 0.15, "post_review": 0.25, "ignore": 0.15, "wait": 0.10, "sell": 0.05},
    "investor": {"invest": 0.35, "ignore": 0.25, "wait": 0.20, "sell": 0.10, "complain": 0.05, "partner": 0.05},
    "competitor": {"compete": 0.30, "sell": 0.15, "ignore": 0.20, "complain": 0.10, "wait": 0.15, "post_review": 0.10},
    "regulator": {"regulate": 0.30, "complain": 0.25, "ignore": 0.15, "wait": 0.20, "post_review": 0.10},
    "employee": {"wait": 0.20, "partner": 0.20, "complain": 0.10, "post_review": 0.15, "buy": 0.10, "ignore": 0.25},
    "partner": {"partner": 0.35, "invest": 0.15, "wait": 0.15, "ignore": 0.15, "buy": 0.10, "complain": 0.10},
    "critic": {"complain": 0.30, "post_review": 0.30, "ignore": 0.15, "wait": 0.15, "sell": 0.10},
    "media": {"post_review": 0.35, "ignore": 0.20, "wait": 0.15, "complain": 0.15, "buy": 0.15},
    "supplier": {"partner": 0.25, "sell": 0.20, "wait": 0.20, "complain": 0.10, "ignore": 0.15, "invest": 0.10},
    "advisor": {"partner": 0.25, "invest": 0.20, "wait": 0.20, "ignore": 0.15, "post_review": 0.10, "buy": 0.10},
}

THOUGHT_TEMPLATES = {
    "buy": [
        "After evaluating the product, I see real potential here. The {trait} in me says it's time to commit.",
        "The value proposition aligns with my needs. As a {role}, I'm ready to make this purchase.",
    ],
    "invest": [
        "The metrics look promising. My {trait} nature drives me to put capital behind this team.",
        "I've seen enough traction to justify an investment at this stage.",
    ],
    "complain": [
        "Something isn't right here. My {trait} instincts are flagging concerns about quality.",
        "As a {role}, I need to voice my dissatisfaction with the current state of things.",
    ],
    "post_review": [
        "Time to share my perspective publicly. My {trait} approach demands transparency.",
        "I have enough data to form an opinion worth sharing.",
    ],
    "partner": [
        "There's clear synergy here. Collaboration would benefit both sides.",
        "My {trait} assessment suggests this partnership could be mutually beneficial.",
    ],
    "sell": [
        "The risk-reward ratio has shifted. Time to exit this position.",
        "Market conditions suggest it's prudent to reduce exposure.",
    ],
    "compete": [
        "The market is there for the taking. Time to make an aggressive move.",
        "I see a vulnerability in their strategy that I can exploit.",
    ],
    "regulate": [
        "Compliance standards must be maintained. I'm issuing a review.",
        "There are regulatory concerns that need to be addressed immediately.",
    ],
    "ignore": [
        "Not enough signal to act on right now. I'll keep monitoring.",
        "The current situation doesn't warrant my immediate attention.",
    ],
    "wait": [
        "Patience is key here. I need more information before acting.",
        "The timing isn't right yet. I'll reassess next cycle.",
    ],
}


def _extract_agent_type(prompt: str) -> str:
    """Extract agent type from the prompt text."""
    prompt_lower = prompt.lower()
    for agent_type in AGENT_TYPE_ACTIONS:
        if agent_type in prompt_lower:
            return agent_type
    return "customer"


def _extract_trait(prompt: str) -> str:
    """Extract a dominant personality trait from the prompt."""
    traits = ["analytical", "aggressive", "cautious", "innovative", "skeptical",
              "optimistic", "risk-tolerant", "conservative", "collaborative", "competitive"]
    prompt_lower = prompt.lower()
    for trait in traits:
        if trait in prompt_lower:
            return trait
    return "thoughtful"


def _extract_role(prompt: str) -> str:
    """Extract role from prompt."""
    match = re.search(r'Your Role:\s*(.+)', prompt)
    if match:
        return match.group(1).strip()
    return "Stakeholder"


def _weighted_choice(weights: Dict[str, float]) -> str:
    """Pick an action based on probability weights."""
    actions = list(weights.keys())
    probs = list(weights.values())
    return random.choices(actions, weights=probs, k=1)[0]


class MockProvider(LLMProvider):
    """Mock LLM provider that generates personality-consistent responses."""

    def completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        agent_type = _extract_agent_type(prompt)
        trait = _extract_trait(prompt)
        role = _extract_role(prompt)

        weights = AGENT_TYPE_ACTIONS.get(agent_type, AGENT_TYPE_ACTIONS["customer"])
        action = _weighted_choice(weights)

        templates = THOUGHT_TEMPLATES.get(action, ["Making a decision based on current conditions."])
        thought = random.choice(templates).format(trait=trait, role=role)

        response = {
            "thought_process": thought,
            "action_type": action,
            "action_details": {
                "target": "startup",
                "content": f"{role} decided to {action} based on {trait} assessment."
            }
        }
        return json.dumps(response)

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        return self.completion(messages[-1]["content"])
