import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("SIM_CITY_DATA_DIR", "data")).absolute()
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR

SIMULATIONS_DIR = DATA_DIR / "simulations"

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

# Model Config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def ensure_directories():
    """Ensure all required data directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SIMULATIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create a layout for logs or other artifacts if needed
    (DATA_DIR / "logs").mkdir(exist_ok=True)

