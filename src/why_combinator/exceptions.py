class WhyCombinatorError(Exception):
    """Base exception for Why-Combinator application."""
    pass

class ConfigError(WhyCombinatorError):
    """Raised when configuration is missing or invalid."""
    pass

class SimulationError(WhyCombinatorError):
    """Raised when simulation execution fails."""
    pass
