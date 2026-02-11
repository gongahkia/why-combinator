
import pytest
import time
import threading
from unittest.mock import MagicMock
from why_combinator.engine.performance import BatchWriter, AgentPool
from why_combinator.models import InteractionLog
from why_combinator.agent.base import BaseAgent

def test_batch_writer_explicit_flush():
    """Test BatchWriter flushes all buffered interactions on explicit flush() call."""
    storage = MagicMock()
    writer = BatchWriter(storage, batch_size=10, flush_interval=100.0)
    
    # Add fewer than batch size
    logs = [InteractionLog(agent_id=f"a{i}", simulation_id="s1", timestamp=i, action="test", target="x", outcome={}) for i in range(5)]
    for log in logs:
        writer.add(log)
        
    # Should not have flushed yet
    assert storage.log_interaction.call_count == 0
    
    # Explicit flush
    writer.flush()
    
    # Should have flushed all 5
    assert storage.log_interaction.call_count == 5
    
    # Verify buffer is empty
    assert len(writer._buffer) == 0

def test_agent_pool_rotation():
    """Test AgentPool rotates agents correctly when pool size exceeds active limit."""
    pool = AgentPool(max_active=2)
    
    a1 = MagicMock()
    a1.entity.id = "1"
    a2 = MagicMock()
    a2.entity.id = "2"
    a3 = MagicMock()
    a3.entity.id = "3"
    
    # Add agents
    pool.add(a1) # active [a1]
    pool.add(a2) # active [a1, a2]
    pool.add(a3) # inactive [a3]
    
    assert pool.active == [a1, a2]
    assert pool.inactive == [a3]
    
    # Rotate 1
    pool.rotate()
    # a1 retires to inactive, a3 promoted to active
    # active: [a2, a3], inactive: [a1]
    assert pool.active[0] == a2
    assert pool.active[1] == a3
    assert pool.inactive[0] == a1
    
    # Rotate 2
    pool.rotate()
    # a2 retires, a1 promoted
    # active: [a3, a1], inactive: [a2]
    assert pool.active[0] == a3
    assert pool.active[1] == a1
    assert pool.inactive[0] == a2

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__]))
