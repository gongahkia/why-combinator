from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


class StakeholderType(str, Enum):
    """Taxonomy of stakeholder types in the simulation."""
    CUSTOMER = "customer"
    COMPETITOR = "competitor"
    INVESTOR = "investor"
    REGULATOR = "regulator"
    EMPLOYEE = "employee"
    PARTNER = "partner"
    CRITIC = "critic"
    # Extended
    MEDIA = "media"
    SUPPLIER = "supplier"
    ADVISOR = "advisor"


class SimulationStage(str, Enum):
    """Lifecycle stages of a startup."""
    IDEA = "idea"
    MVP = "mvp"
    LAUNCH = "launch"
    GROWTH = "growth"
    SCALE = "scale"
    EXIT = "exit"


@dataclass
class UnitEconomics:
    cac: float
    gross_margin: float
    opex_ratio: float
    base_opex: float
    price_per_unit: float

@dataclass
class MarketParams:
    tam: float = 10000.0
    viral_coefficient: float = 0.1
    conversion_rate: float = 0.05
    competitor_count: int = 3
    competitor_quality_avg: float = 0.5
    retention_half_life: float = 200.0
    inflection_tick: int = 100
    revenue_model: str = "transactional"
    investor_burn_limit: float = 15.0

@dataclass
class FundingState:
    initial_capital: float
    revenue_growth_rate: float = 0.05
    burn_growth_rate: float = 0.02


@dataclass
class ExperimentConfig:
    """Typed configuration for reproducible simulation experiments."""
    simulation_name: str
    industry: str
    stage: SimulationStage
    agent_count: int
    market_params: MarketParams
    unit_economics: UnitEconomics
    funding_state: FundingState
    llm_model: str
    seed: Optional[int] = None
    duration_ticks: int = 1000
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentEntity:
    """Represents an AI agent in the simulation."""
    id: str
    type: StakeholderType
    role: str
    personality: Dict[str, Any]  # traits like risk_tolerance, openness, etc.
    knowledge_base: List[str]  # topics or context keys
    behavior_rules: List[str]  # constraints or directives
    name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentEntity':
        # Handle Enum conversion
        if isinstance(data.get('type'), str):
            data['type'] = StakeholderType(data['type'])
        return cls(**data)


@dataclass
class SimulationEntity:
    """Configuration and state for a simulation run."""
    id: str
    name: str
    description: str
    industry: str
    stage: SimulationStage
    parameters: Dict[str, Any]  # e.g., market_size, initial_capital
    created_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SimulationEntity':
        if isinstance(data.get('stage'), str):
            data['stage'] = SimulationStage(data['stage'])
        return cls(**data)


@dataclass
class SimulationRun:
    """Execution record of a simulation."""
    simulation_id: str
    start_time: float
    duration: float  # executed duration in virtual time or seconds?
    status: str  # e.g., running, completed, paused
    results: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InteractionLog:
    """Log entry for agent actions."""
    agent_id: str
    simulation_id: str
    timestamp: float
    action: str
    target: str  # ID of target (agent or system)
    outcome: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class MetricSnapshot:
    """Time-series data point for simulation metrics."""
    simulation_id: str
    timestamp: float
    metric_type: str
    value: float
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
