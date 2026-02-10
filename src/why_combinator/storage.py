from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
from tinydb import TinyDB, Query, where

from why_combinator.models import SimulationEntity, AgentEntity, InteractionLog, MetricSnapshot, SimulationStage
from why_combinator.config import SIMULATIONS_DIR


class StorageManager(ABC):
    """Abstract base class for storage operations."""

    @abstractmethod
    def create_simulation(self, simulation: SimulationEntity) -> str:
        pass

    @abstractmethod
    def get_simulation(self, simulation_id: str) -> Optional[SimulationEntity]:
        pass

    @abstractmethod
    def list_simulations(self) -> List[SimulationEntity]:
        pass

    @abstractmethod
    def save_agent(self, simulation_id: str, agent: AgentEntity) -> None:
        pass

    @abstractmethod
    def get_agents(self, simulation_id: str) -> List[AgentEntity]:
        pass

    @abstractmethod
    def log_interaction(self, log: InteractionLog) -> None:
        pass
    
    @abstractmethod
    def get_interactions(self, simulation_id: str) -> List[InteractionLog]:
        pass

    @abstractmethod
    def log_metric(self, metric: MetricSnapshot) -> None:
        pass
    
    @abstractmethod
    def get_metrics(self, simulation_id: str) -> List[MetricSnapshot]:
        pass


class TinyDBStorageManager(StorageManager):
    """Implementation of StorageManager using TinyDB with one file per simulation."""

    def __init__(self, storage_dir: Path = SIMULATIONS_DIR):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_db_path(self, simulation_id: str) -> Path:
        return self.storage_dir / f"{simulation_id}.json"

    def _get_db(self, simulation_id: str) -> TinyDB:
        return TinyDB(self._get_db_path(simulation_id))

    def create_simulation(self, simulation: SimulationEntity) -> str:
        db = self._get_db(simulation.id)
        metadata_table = db.table('metadata')
        metadata_table.insert(simulation.to_dict())
        db.close()
        return simulation.id

    def get_simulation(self, simulation_id: str) -> Optional[SimulationEntity]:
        path = self._get_db_path(simulation_id)
        if not path.exists():
            return None

        db = TinyDB(path)
        metadata_table = db.table('metadata')
        record = metadata_table.all()[0]
        db.close()
        return SimulationEntity.from_dict(record)

    def list_simulations(self) -> List[SimulationEntity]:
        sims = []
        for file_path in self.storage_dir.glob("*.json"):
            try:
                # Optimized: just read the file content directly for speed if needed, 
                # but TinyDB is safer.
                db = TinyDB(file_path)
                metadata_table = db.table('metadata')
                records = metadata_table.all()
                if records:
                    sims.append(SimulationEntity.from_dict(records[0]))
                db.close()
            except Exception as e:
                # log error or skip malformed files
                print(f"Error reading {file_path}: {e}")
                continue
        return sims

    def save_agent(self, simulation_id: str, agent: AgentEntity) -> None:
        db = self._get_db(simulation_id)
        agents_table = db.table('agents')
        agents_table.upsert(agent.to_dict(), where('id') == agent.id)
        db.close()

    def get_agents(self, simulation_id: str) -> List[AgentEntity]:
        db = self._get_db(simulation_id)
        agents_table = db.table('agents')
        result = [AgentEntity.from_dict(r) for r in agents_table.all()]
        db.close()
        return result

    def log_interaction(self, log: InteractionLog) -> None:
        db = self._get_db(log.simulation_id)
        logs_table = db.table('interactions')
        logs_table.insert(log.to_dict())
        db.close()

    def get_interactions(self, simulation_id: str) -> List[InteractionLog]:
        db = self._get_db(simulation_id)
        logs_table = db.table('interactions')
        result = [InteractionLog(**r) for r in logs_table.all()]
        db.close()
        return result

    def log_metric(self, metric: MetricSnapshot) -> None:
        db = self._get_db(metric.simulation_id)
        metrics_table = db.table('metrics')
        metrics_table.insert(metric.to_dict())
        db.close()

    def get_metrics(self, simulation_id: str) -> List[MetricSnapshot]:
        db = self._get_db(simulation_id)
        metrics_table = db.table('metrics')
        result = [MetricSnapshot(**r) for r in metrics_table.all()]
        db.close()
        return result
