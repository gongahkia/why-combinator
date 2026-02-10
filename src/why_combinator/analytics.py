"""Rich data analytics module for simulation insights."""
import json
import csv
import copy
import random
import io
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from why_combinator.models import SimulationEntity, InteractionLog, MetricSnapshot, ExperimentConfig
from why_combinator.storage import StorageManager

def diff_experiments(config1: ExperimentConfig, config2: ExperimentConfig) -> Dict[str, Any]:
    """Compare two experiment configurations and identify changes."""
    c1 = config1.to_dict()
    c2 = config2.to_dict()
    
    diff = {}
    all_keys = set(c1.keys()) | set(c2.keys())
    
    for key in all_keys:
        val1 = c1.get(key)
        val2 = c2.get(key)
        
        if val1 != val2:
            # Recurse for nested dicts (from nested dataclasses)
            if isinstance(val1, dict) and isinstance(val2, dict):
                sub_diff = {}
                sub_keys = set(val1.keys()) | set(val2.keys())
                for sk in sub_keys:
                    sv1 = val1.get(sk)
                    sv2 = val2.get(sk)
                    if sv1 != sv2:
                        sub_diff[sk] = {"old": sv1, "new": sv2}
                if sub_diff:
                    diff[key] = sub_diff
            else:
                diff[key] = {"old": val1, "new": val2}
                
    return diff

class ScenarioBranch:
    """Represents a what-if scenario branch from a simulation."""
    def __init__(self, base_simulation: SimulationEntity, branch_name: str, parameter_overrides: Dict[str, Any]):
        self.base_id = base_simulation.id
        self.branch_name = branch_name
        self.branched_sim = copy.deepcopy(base_simulation)
        self.branched_sim.parameters.update(parameter_overrides)
        self.results: Dict[str, Any] = {}
    def to_dict(self) -> Dict[str, Any]:
        return {"base_id": self.base_id, "branch_name": self.branch_name, "parameters": self.branched_sim.parameters, "results": self.results}

def compare_simulations(storage: StorageManager, sim_ids: List[str]) -> Dict[str, Any]:
    """Comparative analysis across multiple simulation runs."""
    comparison = {"simulations": [], "metric_comparison": {}}
    all_metric_types = set()
    for sid in sim_ids:
        sim = storage.get_simulation(sid)
        if not sim:
            continue
        metrics = storage.get_metrics(sid)
        interactions = storage.get_interactions(sid)
        latest_metrics = {}
        for m in metrics:
            all_metric_types.add(m.metric_type)
            latest_metrics[m.metric_type] = m.value
        comparison["simulations"].append({
            "id": sid, "name": sim.name, "industry": sim.industry,
            "stage": sim.stage.value, "interactions": len(interactions),
            "metrics": latest_metrics,
        })
    for mt in all_metric_types:
        comparison["metric_comparison"][mt] = {s["name"]: s["metrics"].get(mt, 0) for s in comparison["simulations"]}
    return comparison

def predict_outcome(metrics_history: List[MetricSnapshot], metric_type: str, horizon: int = 10) -> List[float]:
    """Simple linear extrapolation prediction for a metric."""
    values = [m.value for m in metrics_history if m.metric_type == metric_type]
    if len(values) < 2:
        return [values[-1] if values else 0.0] * horizon
    slope = (values[-1] - values[0]) / len(values)
    return [values[-1] + slope * i for i in range(1, horizon + 1)]

def stakeholder_breakdown(storage: StorageManager, simulation_id: str) -> Dict[str, Any]:
    """Generate detailed stakeholder breakdown with demographics."""
    agents = storage.get_agents(simulation_id)
    interactions = storage.get_interactions(simulation_id)
    breakdown = {}
    for agent in agents:
        agent_interactions = [i for i in interactions if i.agent_id == agent.id]
        action_counts = {}
        for i in agent_interactions:
            action_counts[i.action] = action_counts.get(i.action, 0) + 1
        breakdown[agent.name] = {
            "type": agent.type.value, "role": agent.role,
            "total_interactions": len(agent_interactions),
            "action_distribution": action_counts,
            "personality": agent.personality,
        }
    return breakdown

def risk_assessment(storage: StorageManager, simulation_id: str) -> List[Dict[str, Any]]:
    """Create risk assessment report with probability scores."""
    interactions = storage.get_interactions(simulation_id)
    metrics = storage.get_metrics(simulation_id)
    risks = []
    complaint_count = sum(1 for i in interactions if i.action in ("complain", "criticize"))
    total = len(interactions) or 1
    if complaint_count / total > 0.2:
        risks.append({"risk": "High customer dissatisfaction", "probability": min(complaint_count / total, 0.9), "severity": "high", "mitigation": "Improve product quality and support"})
    latest_churn = next((m.value for m in reversed(metrics) if m.metric_type == "churn_rate"), 0)
    if latest_churn > 0.15:
        risks.append({"risk": "Unsustainable churn rate", "probability": min(latest_churn * 2, 0.95), "severity": "critical", "mitigation": "Focus on retention and onboarding"})
    latest_burn = next((m.value for m in reversed(metrics) if m.metric_type == "burn_rate"), 0)
    if latest_burn > 80000:
        risks.append({"risk": "Cash runway concerns", "probability": 0.6, "severity": "high", "mitigation": "Reduce burn or accelerate fundraising"})
    if not risks:
        risks.append({"risk": "No significant risks identified", "probability": 0.0, "severity": "low", "mitigation": "Continue monitoring"})
    return risks

def sensitivity_analysis(simulation: SimulationEntity, base_metrics: Dict[str, float], param_ranges: Optional[Dict[str, Tuple[float, float]]] = None) -> Dict[str, Dict[str, float]]:
    """Analyze how input parameter changes affect outcomes."""
    if param_ranges is None:
        param_ranges = {"market_size": (0.5, 2.0), "initial_capital": (0.5, 2.0), "competition_level": (0.5, 2.0)}
    results = {}
    for param, (low_mult, high_mult) in param_ranges.items():
        results[param] = {}
        for mult in [low_mult, 1.0, high_mult]:
            adjusted_metrics = {}
            for metric, value in base_metrics.items():
                noise = random.uniform(0.9, 1.1)
                if param == "market_size" and metric == "adoption_rate":
                    adjusted_metrics[metric] = value * mult * noise
                elif param == "initial_capital" and metric == "burn_rate":
                    adjusted_metrics[metric] = value / mult * noise
                elif param == "competition_level" and metric == "market_share":
                    adjusted_metrics[metric] = value / mult * noise
                else:
                    adjusted_metrics[metric] = value * noise
            results[param][f"{mult:.1f}x"] = adjusted_metrics
    return results

class CustomMetricBuilder:
    """Let users define custom KPI formulas using safe arithmetic evaluation."""
    def __init__(self):
        self.definitions: Dict[str, str] = {}
    def define(self, name: str, formula: str):
        """Define a custom metric. formula uses metric names as variables, e.g. 'adoption_rate / churn_rate'."""
        self.definitions[name] = formula
    def calculate(self, name: str, metrics: Dict[str, float]) -> float:
        """Calculate a custom metric using safe AST-based evaluation."""
        import ast
        import operator
        formula = self.definitions.get(name)
        if not formula:
            return 0.0
        ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.USub: operator.neg}
        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            elif isinstance(node, ast.Name) and node.id in metrics:
                return float(metrics[node.id])
            elif isinstance(node, ast.BinOp) and type(node.op) in ops:
                left = _eval(node.left)
                right = _eval(node.right)
                if isinstance(node.op, ast.Div) and right == 0:
                    return 0.0
                return ops[type(node.op)](left, right)
            elif isinstance(node, ast.UnaryOp) and type(node.op) in ops:
                return ops[type(node.op)](_eval(node.operand))
            else:
                raise ValueError(f"Unsupported expression: {ast.dump(node)}")
        try:
            tree = ast.parse(formula, mode='eval')
            return float(_eval(tree))
        except Exception:
            return 0.0
    def calculate_all(self, metrics: Dict[str, float]) -> Dict[str, float]:
        return {name: self.calculate(name, metrics) for name in self.definitions}

def export_json(data: Dict[str, Any], path: Path):
    path.write_text(json.dumps(data, indent=2, default=str))

def export_csv(rows: List[Dict[str, Any]], path: Path):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

class SimulationDataWarehouse:
    """Cross-simulation analytics warehouse."""
    def __init__(self, storage: StorageManager):
        self.storage = storage
    def aggregate_metrics(self) -> Dict[str, Dict[str, float]]:
        """Aggregate latest metrics across all simulations."""
        results = {}
        for sim in self.storage.list_simulations():
            metrics = self.storage.get_metrics(sim.id)
            latest = {}
            for m in metrics:
                latest[m.metric_type] = m.value
            results[sim.name] = latest
        return results
    def top_performers(self, metric: str = "adoption_rate", limit: int = 5) -> List[Tuple[str, float]]:
        agg = self.aggregate_metrics()
        ranked = [(name, mets.get(metric, 0)) for name, mets in agg.items()]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:limit]

def calculate_roi(investment: float, metrics: Dict[str, float], months: int = 12) -> Dict[str, float]:
    """Calculate ROI based on simulation outcomes."""
    revenue_proxy = metrics.get("adoption_rate", 0) * metrics.get("market_share", 0) * 1_000_000
    burn = metrics.get("burn_rate", 50000) * months
    net = revenue_proxy * months - burn
    roi = net / investment if investment > 0 else 0
    return {"investment": investment, "projected_revenue": revenue_proxy * months, "total_burn": burn, "net": net, "roi_pct": roi * 100, "months": months}
