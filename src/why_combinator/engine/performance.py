"""Performance optimizations: agent pooling, caching, queuing, batched I/O."""
import threading
import queue
import time
import logging
from typing import List, Dict, Any, Optional
from why_combinator.agent.base import BaseAgent
from why_combinator.models import InteractionLog
from why_combinator.storage import StorageManager

logger = logging.getLogger(__name__)

class AgentPool:
    """Pool and recycle agents to limit concurrent active agents."""
    def __init__(self, max_active: int = 20):
        self.max_active = max_active
        self.active: List[BaseAgent] = []
        self.inactive: List[BaseAgent] = []
    def add(self, agent: BaseAgent):
        if len(self.active) < self.max_active:
            self.active.append(agent)
        else:
            self.inactive.append(agent)
    def rotate(self):
        """Rotate inactive agents into active pool."""
        if self.inactive:
            retired = self.active.pop(0) if len(self.active) >= self.max_active else None
            promoted = self.inactive.pop(0)
            self.active.append(promoted)
            if retired:
                self.inactive.append(retired)
    def get_active(self) -> List[BaseAgent]:
        return self.active

class MemoryCache:
    """In-memory LRU cache using OrderedDict for O(1) access reordering."""
    def __init__(self, max_size: int = 1000):
        from collections import OrderedDict
        self.max_size = max_size
        self._cache: 'OrderedDict[str, Any]' = OrderedDict()
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None
    def set(self, key: str, value: Any):
        if key in self._cache:
            self._cache.move_to_end(key)
        elif len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
        self._cache[key] = value
    def invalidate(self, key: str):
        self._cache.pop(key, None)
    def clear(self):
        self._cache.clear()

class BatchWriter:
    """Batch interaction writes to reduce I/O frequency."""
    def __init__(self, storage: StorageManager, batch_size: int = 50, flush_interval: float = 5.0):
        self.storage = storage
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer: List[InteractionLog] = []
        self._last_flush = time.time()
    def add(self, log: InteractionLog):
        self._buffer.append(log)
        if len(self._buffer) >= self.batch_size or (time.time() - self._last_flush) >= self.flush_interval:
            self.flush()
    def flush(self):
        for log in self._buffer:
            self.storage.log_interaction(log)
        self._buffer.clear()
        self._last_flush = time.time()

class SimulationQueue:
    """Queue for sequential or concurrent simulation runs."""
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._results: Dict[str, Any] = {}
    def enqueue(self, simulation_id: str, params: Dict[str, Any]):
        self._queue.put({"id": simulation_id, "params": params})
    def dequeue(self) -> Optional[Dict[str, Any]]:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None
    def size(self) -> int:
        return self._queue.qsize()
    def store_result(self, simulation_id: str, result: Any):
        self._results[simulation_id] = result
    def get_result(self, simulation_id: str) -> Optional[Any]:
        return self._results.get(simulation_id)

class BackgroundRunner:
    """Run simulations in a background thread."""
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False
    def run_in_background(self, target, *args, **kwargs):
        self._running = True
        self._thread = threading.Thread(target=self._wrap(target), args=args, kwargs=kwargs, daemon=True)
        self._thread.start()
    def _wrap(self, fn):
        def wrapper(*args, **kwargs):
            try:
                fn(*args, **kwargs)
            finally:
                self._running = False
        return wrapper
    @property
    def is_running(self):
        return self._running

def paginate(items: list, page: int = 1, page_size: int = 50) -> list:
    """Paginate a list of items."""
    start = (page - 1) * page_size
    return items[start:start + page_size]

class LazyLoader:
    """Lazy load simulation data on first access."""
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self._loaded: Dict[str, Any] = {}
    def get_simulation(self, sim_id: str):
        if sim_id not in self._loaded:
            self._loaded[sim_id] = self.storage.get_simulation(sim_id)
        return self._loaded[sim_id]
    def invalidate(self, sim_id: str):
        self._loaded.pop(sim_id, None)
