
import pytest
from unittest.mock import MagicMock
from why_combinator.agent.sentiment import SentimentTracker
from why_combinator.agent.emergence import EmergenceDetector
from why_combinator.engine.scenarios import MultiPhaseManager, PHASES, PHASE_THRESHOLDS
from why_combinator.models import SimulationEntity, InteractionLog, SimulationStage
from why_combinator.events import EventBus

def test_sentiment_tracker_scoring():
    """Test SentimentTracker scores."""
    tracker = SentimentTracker()
    agent_id = "agent-1"
    
    # Positive
    tracker.record(agent_id, "I love this product, it is great", 1.0)
    score1 = tracker.get_sentiment(agent_id, window=1)
    assert score1 > 0.0
    
    # Negative
    tracker.record(agent_id, "I hate this, it is terrible and priced high", 2.0)
    score2 = tracker.get_sentiment(agent_id, window=1)
    assert score2 < 0.0
    
    # Neutral/Mixed
    tracker.record(agent_id, "It is okay, mostly fine", 3.0)
    
    # Average
    avg = tracker.get_sentiment(agent_id, window=3)
    # (pos + neg + neutral) / 3
    # rough check
    assert -1.0 <= avg <= 1.0

def test_emergence_detector_repeated_pattern():
    """Test EmergenceDetector flags repeated actions."""
    detector = EmergenceDetector(window_size=10, anomaly_threshold=2.0)
    
    # helper
    def make_log(action):
        return InteractionLog(
            agent_id="a1", simulation_id="s1", timestamp=1.0, 
            action=action, target="t", outcome={}
        )
    
    # Feed 10 "buy" actions
    for _ in range(10):
        detector.observe(make_log("buy"))
        
    # Should flag dominance
    flags = detector.get_flags()
    assert len(flags) > 0
    assert any(f["type"] == "action_dominance" and "buy" in f["description"] for f in flags)
    
    # Reset
    detector.reset()
    assert len(detector.get_flags()) == 0

def test_multiphase_manager_transition():
    """Test phase transition logic."""
    event_bus = EventBus()
    sim = SimulationEntity(
        id="sim-1", name="Test", description="Desc",
        industry="Tech", stage=SimulationStage.IDEA,
        parameters={}, created_at=0.0
    )
    
    manager = MultiPhaseManager(sim, event_bus)
    
    # Idea threshold is 20, adoption needed > 0.1
    
    # 1. Not enough ticks
    metrics = {"adoption_rate": 0.2}
    result = manager.check_transition(tick=10, metrics=metrics)
    assert result is False
    assert sim.stage == SimulationStage.IDEA
    
    # 2. Enough ticks, not enough adoption
    metrics = {"adoption_rate": 0.05}
    result = manager.check_transition(tick=25, metrics=metrics)
    assert result is False
    assert sim.stage == SimulationStage.IDEA
    
    # 3. Both met
    metrics = {"adoption_rate": 0.15}
    result = manager.check_transition(tick=30, metrics=metrics)
    assert result is True
    assert sim.stage == SimulationStage.MVP
    
    # 4. Check next transition (MVP -> Launch)
    # MVP threshold 50, adoption needed > 0.1 * 2 = 0.2
    
    metrics = {"adoption_rate": 0.25}
    result = manager.check_transition(tick=60, metrics=metrics)
    assert result is True
    assert sim.stage == SimulationStage.LAUNCH

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__]))
