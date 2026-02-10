
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

if __name__ == "__main__":
    # verification section
    print("Run with pytest tests/test_cli_integration.py")
