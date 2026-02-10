"""Agent relationship graph tracking alliances, rivalries, dependencies."""
from typing import Dict, List, Tuple, Any
from enum import Enum

class RelationType(str, Enum):
    ALLIANCE = "alliance"
    RIVALRY = "rivalry"
    DEPENDENCY = "dependency"
    NEUTRAL = "neutral"

class RelationshipGraph:
    """Tracks directed relationships between agents."""
    def __init__(self):
        self._edges: Dict[str, Dict[str, Dict[str, Any]]] = {} # source -> target -> {type, strength, history}
    def add_or_update(self, source_id: str, target_id: str, rel_type: RelationType, strength_delta: float = 0.1):
        """Add or update a relationship edge."""
        if source_id not in self._edges:
            self._edges[source_id] = {}
        if target_id not in self._edges[source_id]:
            self._edges[source_id][target_id] = {"type": rel_type.value, "strength": 0.0, "interactions": 0}
        edge = self._edges[source_id][target_id]
        edge["type"] = rel_type.value
        edge["strength"] = max(-1.0, min(1.0, edge["strength"] + strength_delta))
        edge["interactions"] += 1
    def get_relationship(self, source_id: str, target_id: str) -> Dict[str, Any]:
        return self._edges.get(source_id, {}).get(target_id, {"type": "neutral", "strength": 0.0, "interactions": 0})
    def get_allies(self, agent_id: str, threshold: float = 0.3) -> List[str]:
        return [tid for tid, e in self._edges.get(agent_id, {}).items() if e["type"] == "alliance" and e["strength"] >= threshold]
    def get_rivals(self, agent_id: str, threshold: float = 0.3) -> List[str]:
        return [tid for tid, e in self._edges.get(agent_id, {}).items() if e["type"] == "rivalry" and abs(e["strength"]) >= threshold]
    def get_all_edges(self) -> List[Tuple[str, str, Dict[str, Any]]]:
        edges = []
        for src, targets in self._edges.items():
            for tgt, data in targets.items():
                edges.append((src, tgt, data))
        return edges
    def update_from_interaction(self, agent_id: str, target_id: str, action: str):
        """Infer relationship changes from an interaction action."""
        positive_actions = {"invest", "buy", "partner", "send_message", "collaborate"}
        negative_actions = {"complain", "compete", "criticize", "sell"}
        if action in positive_actions:
            self.add_or_update(agent_id, target_id, RelationType.ALLIANCE, strength_delta=0.1)
        elif action in negative_actions:
            self.add_or_update(agent_id, target_id, RelationType.RIVALRY, strength_delta=-0.1)
        else:
            self.add_or_update(agent_id, target_id, RelationType.NEUTRAL, strength_delta=0.0)
    def to_dict(self) -> Dict:
        return self._edges
    def from_dict(self, data: Dict):
        self._edges = data
