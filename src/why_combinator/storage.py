from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import sqlite3
from tinydb import TinyDB, Query, where

from why_combinator.models import SimulationEntity, AgentEntity, InteractionLog, MetricSnapshot, SimulationStage
from why_combinator.config import SIMULATIONS_DIR


class StorageManager(ABC):
    """Abstract base class for storage operations."""

    @abstractmethod
    def create_simulation(self, simulation: SimulationEntity) -> str:
        pass

    @abstractmethod
    def save_simulation(self, simulation: SimulationEntity) -> None:
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

    @abstractmethod
    def query_metrics(self, metric_type: Optional[str] = None, simulation_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Query metrics across simulations with optional filters. Returns aggregated statistics."""
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

    def save_simulation(self, simulation: SimulationEntity) -> None:
        db = self._get_db(simulation.id)
        metadata_table = db.table('metadata')
        metadata_table.truncate()
        metadata_table.insert(simulation.to_dict())
        db.close()

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

    def query_metrics(self, metric_type: Optional[str] = None, simulation_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Query metrics across simulations. Returns aggregated statistics."""
        import statistics
        all_metrics = []
        
        # Get simulations to query
        target_sims = simulation_ids if simulation_ids else [s.id for s in self.list_simulations()]
        
        for sim_id in target_sims:
            if not self._get_db_path(sim_id).exists():
                continue
            db = self._get_db(sim_id)
            metrics_table = db.table('metrics')
            if metric_type:
                all_metrics.extend([MetricSnapshot(**r) for r in metrics_table.search(where('metric_type') == metric_type)])
            else:
                all_metrics.extend([MetricSnapshot(**r) for r in metrics_table.all()])
            db.close()
        
        if not all_metrics:
            return {"count": 0, "metrics": []}
        
        # Group by metric type
        by_type: Dict[str, List[float]] = {}
        for m in all_metrics:
            if m.metric_type not in by_type:
                by_type[m.metric_type] = []
            by_type[m.metric_type].append(m.value)
        
        # Calculate statistics
        stats = {}
        for mtype, values in by_type.items():
            stats[mtype] = {
                "count": len(values),
                "mean": statistics.mean(values) if values else 0,
                "median": statistics.median(values) if values else 0,
                "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0
            }
        
        return {
            "count": len(all_metrics),
            "simulations_queried": len(target_sims),
            "metric_types": list(by_type.keys()),
            "statistics": stats
        }


class SqliteStorageManager(StorageManager):
    """Implementation of StorageManager using SQLite with one database file for all simulations."""

    def __init__(self, storage_dir: Path = SIMULATIONS_DIR):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / "simulations.db"
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Initialize database schema with tables and indexes."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Simulations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                industry TEXT NOT NULL,
                stage TEXT NOT NULL,
                description TEXT,
                config_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        
        # Agents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                sim_id TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                type TEXT NOT NULL,
                personality_json TEXT NOT NULL,
                FOREIGN KEY (sim_id) REFERENCES simulations(id)
            )
        """)
        
        # Interactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sim_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                target TEXT,
                details_json TEXT,
                timestamp REAL NOT NULL,
                FOREIGN KEY (sim_id) REFERENCES simulations(id)
            )
        """)
        
        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sim_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (sim_id) REFERENCES simulations(id)
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_sim_tick ON interactions(sim_id, tick)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_sim_type ON metrics(sim_id, metric_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_sim ON agents(sim_id)")
        
        conn.commit()
        conn.close()

    def create_simulation(self, simulation: SimulationEntity) -> str:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO simulations (id, name, industry, stage, description, config_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            simulation.id,
            simulation.name,
            simulation.industry,
            simulation.stage.value,
            simulation.description,
            json.dumps(simulation.parameters),
            simulation.created_at
        ))
        conn.commit()
        conn.close()
        return simulation.id

    def save_simulation(self, simulation: SimulationEntity) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO simulations (id, name, industry, stage, description, config_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            simulation.id,
            simulation.name,
            simulation.industry,
            simulation.stage.value,
            simulation.description,
            json.dumps(simulation.parameters),
            simulation.created_at
        ))
        conn.commit()
        conn.close()

    def get_simulation(self, simulation_id: str) -> Optional[SimulationEntity]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM simulations WHERE id = ?", (simulation_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return SimulationEntity(
            id=row["id"],
            name=row["name"],
            industry=row["industry"],
            stage=SimulationStage(row["stage"]),
            description=row["description"],
            parameters=json.loads(row["config_json"]),
            created_at=row["created_at"]
        )

    def list_simulations(self) -> List[SimulationEntity]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM simulations ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [
            SimulationEntity(
                id=row["id"],
                name=row["name"],
                industry=row["industry"],
                stage=SimulationStage(row["stage"]),
                description=row["description"],
                parameters=json.loads(row["config_json"]),
                created_at=row["created_at"]
            )
            for row in rows
        ]

    def save_agent(self, simulation_id: str, agent: AgentEntity) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO agents (id, sim_id, name, role, type, personality_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            agent.id,
            simulation_id,
            agent.name,
            agent.role,
            agent.type.value,
            json.dumps({
                "personality": agent.personality,
                "knowledge_base": agent.knowledge_base,
                "behavior_rules": agent.behavior_rules
            })
        ))
        conn.commit()
        conn.close()

    def get_agents(self, simulation_id: str) -> List[AgentEntity]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE sim_id = ?", (simulation_id,))
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            data = json.loads(row["personality_json"])
            from why_combinator.models import AgentType
            result.append(AgentEntity(
                id=row["id"],
                name=row["name"],
                role=row["role"],
                type=AgentType(row["type"]),
                personality=data.get("personality", {}),
                knowledge_base=data.get("knowledge_base", {}),
                behavior_rules=data.get("behavior_rules", {})
            ))
        return result

    def log_interaction(self, log: InteractionLog) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        # Extract tick from log if available, otherwise default to 0
        tick = log.outcome.get("tick", 0) if isinstance(log.outcome, dict) else 0
        cursor.execute("""
            INSERT INTO interactions (sim_id, agent_id, tick, action_type, target, details_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            log.simulation_id,
            log.agent_id,
            tick,
            log.action,
            log.target,
            json.dumps(log.outcome),
            log.timestamp
        ))
        conn.commit()
        conn.close()

    def get_interactions(self, simulation_id: str) -> List[InteractionLog]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM interactions WHERE sim_id = ? ORDER BY timestamp", (simulation_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            InteractionLog(
                simulation_id=row["sim_id"],
                agent_id=row["agent_id"],
                timestamp=row["timestamp"],
                action=row["action_type"],
                target=row["target"],
                outcome=json.loads(row["details_json"]) if row["details_json"] else {}
            )
            for row in rows
        ]

    def log_metric(self, metric: MetricSnapshot) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        # Extract tick from metric parameters if available
        tick = 0
        cursor.execute("""
            INSERT INTO metrics (sim_id, tick, metric_type, value, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            metric.simulation_id,
            tick,
            metric.metric_type,
            metric.value,
            metric.timestamp
        ))
        conn.commit()
        conn.close()

    def get_metrics(self, simulation_id: str) -> List[MetricSnapshot]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM metrics WHERE sim_id = ? ORDER BY timestamp", (simulation_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            MetricSnapshot(
                simulation_id=row["sim_id"],
                timestamp=row["timestamp"],
                metric_type=row["metric_type"],
                value=row["value"]
            )
            for row in rows
        ]

    def query_metrics(self, metric_type: Optional[str] = None, simulation_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Query metrics across simulations with SQL aggregation."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT 
                metric_type,
                COUNT(*) as count,
                AVG(value) as mean,
                MIN(value) as min,
                MAX(value) as max,
                COUNT(DISTINCT sim_id) as sim_count
            FROM metrics
            WHERE 1=1
        """
        params = []
        
        if metric_type:
            query += " AND metric_type = ?"
            params.append(metric_type)
        
        if simulation_ids:
            placeholders = ",".join("?" * len(simulation_ids))
            query += f" AND sim_id IN ({placeholders})"
            params.extend(simulation_ids)
        
        query += " GROUP BY metric_type"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM metrics WHERE 1=1"
        count_params = []
        if metric_type:
            count_query += " AND metric_type = ?"
            count_params.append(metric_type)
        if simulation_ids:
            placeholders = ",".join("?" * len(simulation_ids))
            count_query += f" AND sim_id IN ({placeholders})"
            count_params.extend(simulation_ids)
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()["total"]
        
        conn.close()
        
        # Calculate standard deviation manually (SQLite doesn't have STDDEV)
        stats = {}
        for row in rows:
            mtype = row["metric_type"]
            stats[mtype] = {
                "count": row["count"],
                "mean": row["mean"],
                "min": row["min"],
                "max": row["max"],
                "stdev": 0  # Would need second pass to calculate
            }
        
        return {
            "count": total_count,
            "simulations_queried": row["sim_count"] if rows else 0,
            "metric_types": list(stats.keys()),
            "statistics": stats
        }


def get_storage_manager(backend: Optional[str] = None) -> StorageManager:
    """Factory function to create storage manager based on config."""
    from why_combinator.config import STORAGE_BACKEND
    
    backend_type = backend or STORAGE_BACKEND
    
    if backend_type == "sqlite":
        return SqliteStorageManager()
    elif backend_type == "tinydb":
        return TinyDBStorageManager()
    else:
        raise ValueError(f"Unknown storage backend: {backend_type}. Must be 'sqlite' or 'tinydb'.")


def migrate_tinydb_to_sqlite(source_dir: Optional[Path] = None, dest_dir: Optional[Path] = None) -> None:
    """Migrate data from TinyDB to SQLite storage backend."""
    import logging
    logger = logging.getLogger(__name__)
    
    source_storage = TinyDBStorageManager(source_dir or SIMULATIONS_DIR)
    dest_storage = SqliteStorageManager(dest_dir or SIMULATIONS_DIR)
    
    simulations = source_storage.list_simulations()
    logger.info(f"Found {len(simulations)} simulations to migrate")
    
    for sim in simulations:
        logger.info(f"Migrating simulation: {sim.id} - {sim.name}")
        
        # Create simulation in SQLite
        dest_storage.create_simulation(sim)
        
        # Migrate agents
        agents = source_storage.get_agents(sim.id)
        for agent in agents:
            dest_storage.save_agent(sim.id, agent)
        logger.info(f"  Migrated {len(agents)} agents")
        
        # Migrate interactions
        interactions = source_storage.get_interactions(sim.id)
        for interaction in interactions:
            dest_storage.log_interaction(interaction)
        logger.info(f"  Migrated {len(interactions)} interactions")
        
        # Migrate metrics
        metrics = source_storage.get_metrics(sim.id)
        for metric in metrics:
            dest_storage.log_metric(metric)
        logger.info(f"  Migrated {len(metrics)} metrics")
    
    logger.info(f"Migration complete: {len(simulations)} simulations migrated to SQLite")



