import os
import logging
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file if it exists
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("WHY_COMBINATOR_DATA_DIR", "data")).absolute()
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR

SIMULATIONS_DIR = DATA_DIR / "simulations"

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

# Model Config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Storage Config
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "sqlite")  # "tinydb" or "sqlite"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "human")  # "human" or "json"


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "simulation_id"):
            log_data["simulation_id"] = record.simulation_id
        if hasattr(record, "tick"):
            log_data["tick"] = record.tick
        if hasattr(record, "agent_id"):
            log_data["agent_id"] = record.agent_id
        if hasattr(record, "action_type"):
            log_data["action_type"] = record.action_type
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        
        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def configure_logging(level: Optional[str] = None, format_type: Optional[str] = None) -> None:
    """
    Configure centralized logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to LOG_LEVEL env var.
        format_type: "human" for human-readable or "json" for structured JSON. Defaults to LOG_FORMAT env var.
    """
    log_level = level or LOG_LEVEL
    log_format = format_type or LOG_FORMAT
    
    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # Set formatter based on format type
    if log_format.lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def ensure_directories():
    """Ensure all required data directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SIMULATIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create a layout for logs or other artifacts if needed
    (DATA_DIR / "logs").mkdir(exist_ok=True)

