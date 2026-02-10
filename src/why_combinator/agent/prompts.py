from typing import List, Dict, Any, Optional
import json

class PromptTemplate:
    """Template for agent prompts."""
    def __init__(self, template: str):
        self.template = template

    def render(self, Context: Dict[str, Any]) -> str:
        return self.template.format(**Context)


# Simulation context injected into every prompt
SIMULATION_CONTEXT = """
You are an agent in a startup simulation called Why-Combinator.
Current Industry: {industry}
Current Startup Stage: {stage}
Startup Name: {startup_name}
Startup Description: {startup_description}

Current Date: {date}
"""

# Base identity for all agents
AGENT_IDENTITY = """
Your Name: {name}
Your Role: {role}
Your Type: {type}

Your Personality Traits:
{personality}

Your Knowledge Base:
{knowledge_base}

Your Core Behavior Rules:
{behavior_rules}
"""

# Task-specific prompts
DECISION_PROMPT = """
SITUATION:
{world_state}

RECENT MEMORY:
{memory}

TASK:
Based on your role and personality, analyze the situation and decide on your next action.
You must output a JSON object with the following structure:
{{
    "thought_process": "Your internal reasoning...",
    "action_type": "The type of action (e.g., 'buy', 'post_review', 'invest', 'ignore', 'complain')",
    "action_details": {{
        "content": "The content of your action (e.g. review text, email body, etc.)",
        "target": "Target entity ID or name",
        "parameters": {{ "amount": 1000, "rating": 5 }}
    }}
}}

Ensure your action is consistent with your personality: {personality_summary}
"""

# Specific Prompts for specific types can inherit or compose these.
CUSTOMER_EVALUATION_PROMPT = """
You are evaluating the product "{product_name}".
Product Description: {product_description}
Price: {price}

Considering your needs and personality, do you buy it?
Write a review or decision.
"""

# Memory summarization prompt for LLM-based memory compression
MEMORY_SUMMARIZATION_PROMPT = """
Summarize the following {count} agent memories into a concise 2-3 sentence summary that captures the key events and patterns:

MEMORIES:
{memories}

Provide only the summary, no additional commentary.
"""
