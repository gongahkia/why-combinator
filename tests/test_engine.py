"""Tests for SimulationEngine: state transitions, step, checkpoint/restore."""
from why_combinator.engine.core import SimulationEngine


def test_engine_start_stop(sample_simulation, mock_storage):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    engine = SimulationEngine(sim, mock_storage)
    assert not engine.is_running
    engine.start()
    assert engine.is_running
    engine.stop()
    assert not engine.is_running


def test_engine_pause_resume(sample_simulation, mock_storage):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    engine = SimulationEngine(sim, mock_storage)
    engine.start()
    engine.pause()
    assert engine.is_paused
    engine.resume()
    assert not engine.is_paused
    engine.stop()


async def test_engine_step_increments_tick(sample_simulation, mock_storage):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    engine = SimulationEngine(sim, mock_storage)
    engine.start()
    assert engine.tick_count == 0
    await engine.step()
    assert engine.tick_count == 1
    await engine.step()
    assert engine.tick_count == 2
    engine.stop()


async def test_engine_step_while_paused_is_noop(sample_simulation, mock_storage):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    engine = SimulationEngine(sim, mock_storage)
    engine.start()
    engine.pause()
    await engine.step()
    assert engine.tick_count == 0
    engine.stop()


async def test_engine_checkpoint_restore(sample_simulation, mock_storage):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    engine = SimulationEngine(sim, mock_storage)
    engine.start()
    for _ in range(5):
        await engine.step()
    engine.checkpoint()
    engine.stop()
    sim2 = mock_storage.get_simulation(sim.id)
    engine2 = SimulationEngine(sim2, mock_storage)
    restored = engine2.restore_from_checkpoint()
    assert restored
    assert engine2.tick_count == 5
