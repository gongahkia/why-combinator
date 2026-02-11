
import pytest
from why_combinator.agent.relationships import RelationshipGraph, RelationType
from why_combinator.agent.coalition import CoalitionManager

def test_relationship_decay():
    """Test that relationship strength decays over time."""
    graph = RelationshipGraph()
    # A allied with B, updates to 0.5
    for _ in range(5):
        graph.add_or_update("A", "B", RelationType.ALLIANCE, strength_delta=0.1)
    
    initial_strength = graph.get_relationship("A", "B")["strength"]
    assert initial_strength >= 0.5
    for _ in range(100):
        graph.tick(decay_factor=0.99)
    final_strength = graph.get_relationship("A", "B")["strength"]
    assert final_strength < initial_strength
    assert final["strength"] > 0.0 # Should not be zero yet

def test_coalition_detection_mutual():
    """Test detection of coalition with mutual relationships."""
    graph = RelationshipGraph()
    manager = CoalitionManager()
    
    agents = ["A", "B", "C", "D"]
    
    # Create triangle A-B-C mutual alliance
    # A <-> B
    graph.add_or_update("A", "B", RelationType.ALLIANCE, strength_delta=0.5)
    graph.add_or_update("B", "A", RelationType.ALLIANCE, strength_delta=0.5)
    
    # B <-> C
    graph.add_or_update("B", "C", RelationType.ALLIANCE, strength_delta=0.5)
    graph.add_or_update("C", "B", RelationType.ALLIANCE, strength_delta=0.5)
    
    # A <-> C
    graph.add_or_update("A", "C", RelationType.ALLIANCE, strength_delta=0.5)
    graph.add_or_update("C", "A", RelationType.ALLIANCE, strength_delta=0.5)
    
    # D is isolated
    
    coalitions = manager.detect_coalitions(graph, agents, min_strength=0.3)
    
    assert len(coalitions) == 1
    c = coalitions[0]
    assert len(c.members) == 3
    assert "A" in c.members
    assert "B" in c.members
    assert "C" in c.members
    assert "D" not in c.members

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__]))
