from typing import Callable, List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """A simulation event."""
    type: str
    payload: Dict[str, Any]
    timestamp: float
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class EventBus:
    """Simple synchronous event bus for simulation events."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}
        self._all_subscribers: List[Callable[[Event], None]] = []

    def subscribe(self, event_type: str, callback: Callable[[Event], None]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: Callable[[Event], None]):
        self._all_subscribers.append(callback)

    def publish(self, event_type: str, payload: Dict[str, Any], timestamp: float):
        event = Event(type=event_type, payload=payload, timestamp=timestamp)
        logger.debug(f"Event published: {event_type} at {timestamp}")
        
        # Notify specific subscribers
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")

        # Notify global subscribers
        for callback in self._all_subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {e}")
