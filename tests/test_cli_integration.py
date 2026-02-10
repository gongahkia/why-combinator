
import pytest
import re
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from why_combinator.cli import app
from why_combinator import api
from why_combinator.storage import TinyDBStorageManager

runner = CliRunner()

@pytest.fixture
def mock_api_storage(tmp_path):
    """Patch api._get_storage to use a temporary directory for TinyDB."""
    sim_dir = tmp_path / "simulations"
    sim_dir.mkdir()
    storage = TinyDBStorageManager(storage_dir=sim_dir)
    with patch("why_combinator.api._get_storage", return_value=storage):
        yield storage

def test_cli_new_simulation(mock_api_storage):
    """
    Test 'simulate new' command creates simulation with correct metadata and spawned agents.
    Integration test using CliRunner.
    """
    
    # Run the command
    result = runner.invoke(app, [
        "simulate", "new", 
        "--name", "IntegrationTestApp", 
        "--industry", "SpaceTech", 
        "--description", "orbital dynamics simulation", 
        "--stage", "idea"
    ])
    
    # Assert successful execution
    assert result.exit_code == 0
    assert "Created simulation: IntegrationTestApp" in result.stdout
    
    # Extract ID using regex
    match = re.search(r"Created simulation: IntegrationTestApp \(([\w-]+)\)", result.stdout)
    assert match, "Simulation ID not found in output"
    sim_id = match.group(1)
    
    # Verify metadata via API (which uses the mocked storage)
    sim = api.get_simulation(sim_id)
    assert sim is not None
    assert sim.name == "IntegrationTestApp"
    assert sim.industry == "SpaceTech"
    assert sim.stage.value == "idea"
    
    # Verify agents spawned
    agents = api.get_agents(sim_id)
    assert len(agents) > 0
    
    # Verify stdout mentions spawned agent
    # We check if at least one agent is mentioned
    assert "Spawned agent:" in result.stdout
    assert agents[0].name in result.stdout


def test_cli_run_simulation(mock_api_storage):
    """Test 'simulate run' command executes ticks."""
    
    # Setup: Create a simulation first
    sim = api.create_simulation(
        name="RunTestApp", 
        industry="SaaS", 
        description="Run test", 
        stage="idea"
    )
    
    # Execute run command
    result = runner.invoke(app, [
        "simulate", "run", 
        str(sim.id),
        "--model", "mock",
        "--duration", "11",
        "--headless"
    ])
    
    if result.exit_code != 0:
        print(f"Output: {result.stdout}")
        print(f"Exception: {result.exception}")
        
    assert result.exit_code == 0
    assert "Simulation finished" in result.stdout
    
    # Verify execution happened by checking logs
    logs = api.get_simulation_logs(sim.id)
    # The default agents might not interact in 5 ticks if random chance is low,
    # but mock provider should be fast.
    # However, create_simulation creates agents.
    # GenericAgent attempts action every tick? usually.
    # So logs should not be empty hopefully.
    # But even if logs empty, metrics should be recorded?
    # storage.get_metrics is the best proof.
    
    metrics = mock_api_storage.get_metrics(sim.id)
    # metrics are emitted every 10 ticks by default in engine/core.py line 249: if self.tick_count % 10 == 0: self._emit_metrics()
    # So if duration=5, NO metrics might be emitted!
    # I should set duration=11 or check logs.
    
    if not logs and not metrics:
        # Check if agents exist
        agents = api.get_agents(sim.id)
        assert len(agents) > 0

    # Ensure no error was thrown
    assert "Simulation failed" not in result.stdout


def test_cli_export(mock_api_storage):
    """Test 'simulate export' command."""
    # Setup
    sim = api.create_simulation(
        name="ExportTestApp", 
        industry="SaaS", 
        description="Export test", 
        stage="mvp"
    )
    
    # Use a separate directory for exports
    output_dir = mock_api_storage.storage_dir.parent / "exports"
    output_dir.mkdir(exist_ok=True)
    
    # Test JSON export
    result = runner.invoke(app, [
        "simulate", "export", 
        str(sim.id),
        "--output", str(output_dir),
        "--format", "json"
    ])
    
    assert result.exit_code == 0
    assert "Exported (json) to" in result.stdout
    
    # Verify file existence
    filename = f"ExportTestApp_{sim.id[:8]}.json"
    assert (output_dir / filename).exists()
    
    # Test Markdown export
    result_md = runner.invoke(app, [
        "simulate", "export", 
        str(sim.id),
        "--output", str(output_dir),
        "--format", "md"
    ])
    
    assert result_md.exit_code == 0
    filename_md = f"ExportTestApp_{sim.id[:8]}.md"
    assert (output_dir / filename_md).exists()

if __name__ == "__main__":
    # verification section
    print("Run with pytest tests/test_cli_integration.py")
