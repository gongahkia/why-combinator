"""Agent coalition formation - groups with shared interests."""
from typing import List, Dict, Any, Set
from sim_city.agent.relationships import RelationshipGraph

class Coalition:
    """A group of agents with shared interests."""
    def __init__(self, name: str, members: Set[str]):
        self.name = name
        self.members = members
        self.strength: float = 0.0
    def add_member(self, agent_id: str):
        self.members.add(agent_id)
    def remove_member(self, agent_id: str):
        self.members.discard(agent_id)
    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "members": list(self.members), "strength": self.strength}

class CoalitionManager:
    """Detects and manages coalitions based on relationship graph."""
    def __init__(self):
        self.coalitions: List[Coalition] = []
    def detect_coalitions(self, graph: RelationshipGraph, agent_ids: List[str], min_strength: float = 0.3) -> List[Coalition]:
        """Detect coalitions from mutual alliances in the relationship graph."""
        visited: Set[str] = set()
        new_coalitions = []
        for agent_id in agent_ids:
            if agent_id in visited:
                continue
            allies = set(graph.get_allies(agent_id, threshold=min_strength))
            if not allies:
                continue
            cluster = {agent_id}
            frontier = list(allies)
            while frontier:
                ally = frontier.pop()
                if ally in cluster:
                    continue
                cluster.add(ally)
                sub_allies = set(graph.get_allies(ally, threshold=min_strength))
                overlap = sub_allies & (set(agent_ids) - cluster)
                frontier.extend(overlap)
            if len(cluster) >= 2:
                visited.update(cluster)
                coalition = Coalition(name=f"Coalition-{len(new_coalitions)+1}", members=cluster)
                coalition.strength = sum(graph.get_relationship(a, b)["strength"] for a in cluster for b in cluster if a != b) / max(len(cluster) * (len(cluster) - 1), 1)
                new_coalitions.append(coalition)
        self.coalitions = new_coalitions
        return new_coalitions
    def get_agent_coalition(self, agent_id: str) -> str:
        for c in self.coalitions:
            if agent_id in c.members:
                return c.name
        return ""
    def to_dict(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.coalitions]
