"""Advanced analytics & AI: LLM insights, pattern recognition, recommendations, anomaly detection."""
import random
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from sim_city.models import InteractionLog, MetricSnapshot, SimulationEntity
from sim_city.llm.base import LLMProvider
from sim_city.utils.parsing import extract_json
from sim_city.storage import StorageManager

logger = logging.getLogger(__name__)

def llm_insight_generation(llm: LLMProvider, simulation: SimulationEntity, metrics: Dict[str, float], interactions: List[InteractionLog]) -> Dict[str, Any]:
    """Use LLM to generate insights from simulation data."""
    action_summary = Counter(i.action for i in interactions).most_common(5)
    prompt = f"""Analyze this startup simulation data and provide strategic insights:
Startup: {simulation.name} ({simulation.industry}, stage: {simulation.stage.value})
Metrics: {json.dumps(metrics)}
Top actions: {action_summary}
Total interactions: {len(interactions)}
Provide JSON: {{"key_insights": ["insight1", "insight2", "insight3"], "risks": ["risk1"], "opportunities": ["opp1"], "recommendation": "one sentence"}}"""
    response = llm.completion(prompt, system_prompt="You are a startup strategy analyst.")
    return extract_json(response) or {"key_insights": ["Insufficient data for analysis"], "risks": [], "opportunities": [], "recommendation": "Gather more data"}

def pattern_recognition(interactions: List[InteractionLog]) -> Dict[str, Any]:
    """Identify success/failure patterns from interaction history."""
    action_counts = Counter(i.action for i in interactions)
    total = len(interactions) or 1
    patterns = {"success_indicators": [], "failure_indicators": [], "neutral_patterns": []}
    positive_actions = {"buy", "invest", "partner", "collaborate"}
    negative_actions = {"complain", "sell", "criticize", "ignore"}
    pos_ratio = sum(action_counts.get(a, 0) for a in positive_actions) / total
    neg_ratio = sum(action_counts.get(a, 0) for a in negative_actions) / total
    if pos_ratio > 0.3:
        patterns["success_indicators"].append(f"High positive action ratio ({pos_ratio:.0%})")
    if neg_ratio > 0.3:
        patterns["failure_indicators"].append(f"High negative action ratio ({neg_ratio:.0%})")
    if action_counts.get("invest", 0) > 2:
        patterns["success_indicators"].append("Multiple investment actions suggest strong interest")
    if action_counts.get("complain", 0) / total > 0.2:
        patterns["failure_indicators"].append("High complaint rate indicates product issues")
    action_diversity = len(action_counts) / max(total, 1)
    if action_diversity > 0.3:
        patterns["success_indicators"].append("Diverse agent actions suggest healthy ecosystem")
    else:
        patterns["neutral_patterns"].append("Low action diversity - may indicate stagnation")
    return patterns

def recommendation_engine(metrics: Dict[str, float], patterns: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate strategic recommendations based on metrics and patterns."""
    recommendations = []
    if metrics.get("churn_rate", 0) > 0.15:
        recommendations.append({"priority": "high", "action": "Focus on retention", "rationale": "Churn rate is above healthy threshold"})
    if metrics.get("adoption_rate", 0) < 0.1:
        recommendations.append({"priority": "high", "action": "Improve product-market fit", "rationale": "Adoption rate is very low"})
    if metrics.get("burn_rate", 0) > 80000:
        recommendations.append({"priority": "medium", "action": "Optimize unit economics", "rationale": "Burn rate may threaten runway"})
    if metrics.get("market_share", 0) < 0.02:
        recommendations.append({"priority": "medium", "action": "Increase marketing/sales", "rationale": "Minimal market penetration"})
    if len(patterns.get("success_indicators", [])) > len(patterns.get("failure_indicators", [])):
        recommendations.append({"priority": "low", "action": "Double down on current strategy", "rationale": "More positive than negative signals"})
    if not recommendations:
        recommendations.append({"priority": "low", "action": "Continue current strategy", "rationale": "No urgent concerns identified"})
    return recommendations

def anomaly_detection(metrics_history: List[MetricSnapshot], threshold: float = 2.0) -> List[Dict[str, Any]]:
    """Detect unexpected metric values using simple z-score-like method."""
    by_type: Dict[str, List[float]] = {}
    for m in metrics_history:
        by_type.setdefault(m.metric_type, []).append(m.value)
    anomalies = []
    for metric_type, values in by_type.items():
        if len(values) < 5:
            continue
        mean = sum(values) / len(values)
        std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
        if std == 0:
            continue
        latest = values[-1]
        z = abs(latest - mean) / std
        if z > threshold:
            anomalies.append({"metric": metric_type, "value": latest, "mean": mean, "std": std, "z_score": z, "direction": "above" if latest > mean else "below"})
    return anomalies

def predictive_success_scoring(metrics: Dict[str, float], interactions: List[InteractionLog]) -> Dict[str, Any]:
    """Score likelihood of success with confidence intervals."""
    score = 50.0 # base score
    if metrics.get("adoption_rate", 0) > 0.2:
        score += 15
    if metrics.get("churn_rate", 0) < 0.1:
        score += 10
    if metrics.get("market_share", 0) > 0.05:
        score += 10
    if metrics.get("burn_rate", 0) < 50000:
        score += 5
    positive_ratio = sum(1 for i in interactions if i.action in ("buy", "invest", "partner")) / max(len(interactions), 1)
    score += positive_ratio * 20
    score = min(max(score, 0), 100)
    confidence = min(len(interactions) / 100, 1.0) * 0.8 # more data = more confidence, max 80%
    margin = (1 - confidence) * 20
    return {"score": round(score, 1), "confidence": round(confidence, 2), "lower_bound": round(max(score - margin, 0), 1), "upper_bound": round(min(score + margin, 100), 1), "interpretation": "Strong" if score > 70 else "Moderate" if score > 40 else "Weak"}

def causal_inference(interactions: List[InteractionLog], metrics_history: List[MetricSnapshot]) -> List[Dict[str, Any]]:
    """Rough causal inference: which actions correlated with metric changes."""
    if len(metrics_history) < 10:
        return [{"finding": "Insufficient data for causal analysis"}]
    by_type: Dict[str, List[Tuple[float, float]]] = {}
    for m in metrics_history:
        by_type.setdefault(m.metric_type, []).append((m.timestamp, m.value))
    findings = []
    action_counts_by_window: Dict[str, Dict[str, int]] = {}
    for metric_type, ts_vals in by_type.items():
        if len(ts_vals) < 4:
            continue
        half = len(ts_vals) // 2
        first_avg = sum(v for _, v in ts_vals[:half]) / half
        second_avg = sum(v for _, v in ts_vals[half:]) / (len(ts_vals) - half)
        change = second_avg - first_avg
        first_time = ts_vals[0][0]
        mid_time = ts_vals[half][0]
        early_actions = Counter(i.action for i in interactions if i.timestamp < mid_time)
        late_actions = Counter(i.action for i in interactions if i.timestamp >= mid_time)
        for action in set(list(early_actions.keys()) + list(late_actions.keys())):
            early_count = early_actions.get(action, 0)
            late_count = late_actions.get(action, 0)
            if late_count > early_count * 1.5 and abs(change) > 0.01:
                direction = "increase" if change > 0 else "decrease"
                findings.append({"action": action, "metric": metric_type, "correlation": direction, "action_increase": f"{early_count}->{late_count}", "metric_change": f"{first_avg:.3f}->{second_avg:.3f}"})
    return findings or [{"finding": "No clear causal relationships detected"}]

class ReinforcementLearner:
    """Simple Q-learning-inspired agent behavior optimizer."""
    def __init__(self, actions: List[str], learning_rate: float = 0.1, discount: float = 0.9):
        self.q_table: Dict[str, Dict[str, float]] = {} # state -> action -> value
        self.lr = learning_rate
        self.discount = discount
        self.actions = actions
    def get_state_key(self, metrics: Dict[str, float]) -> str:
        bins = {k: "high" if v > 0.5 else "low" for k, v in metrics.items()}
        return json.dumps(bins, sort_keys=True)
    def choose_action(self, state: str, epsilon: float = 0.1) -> str:
        if random.random() < epsilon or state not in self.q_table:
            return random.choice(self.actions)
        return max(self.q_table[state], key=self.q_table[state].get)
    def update(self, state: str, action: str, reward: float, next_state: str):
        if state not in self.q_table:
            self.q_table[state] = {a: 0.0 for a in self.actions}
        if next_state not in self.q_table:
            self.q_table[next_state] = {a: 0.0 for a in self.actions}
        best_next = max(self.q_table[next_state].values())
        self.q_table[state][action] += self.lr * (reward + self.discount * best_next - self.q_table[state][action])

def meta_analysis(storage: StorageManager) -> Dict[str, Any]:
    """Cross-simulation meta-analysis."""
    sims = storage.list_simulations()
    if not sims:
        return {"finding": "No simulations to analyze"}
    industry_performance: Dict[str, List[float]] = {}
    stage_performance: Dict[str, List[float]] = {}
    for sim in sims:
        metrics = storage.get_metrics(sim.id)
        adoption = next((m.value for m in reversed(metrics) if m.metric_type == "adoption_rate"), 0)
        industry_performance.setdefault(sim.industry, []).append(adoption)
        stage_performance.setdefault(sim.stage.value, []).append(adoption)
    return {
        "total_simulations": len(sims),
        "industry_avg_adoption": {k: sum(v) / len(v) for k, v in industry_performance.items()},
        "stage_avg_adoption": {k: sum(v) / len(v) for k, v in stage_performance.items()},
        "best_performing_industry": max(industry_performance, key=lambda k: sum(industry_performance[k]) / len(industry_performance[k])) if industry_performance else "N/A",
    }
