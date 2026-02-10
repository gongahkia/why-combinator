"""Simple keyword-based sentiment analysis for agent actions."""
from typing import List, Dict, Any, Tuple
from collections import defaultdict

POSITIVE_KEYWORDS = {"buy", "invest", "partner", "collaborate", "love", "great", "excellent", "recommend", "approve", "support", "innovative", "promising"}
NEGATIVE_KEYWORDS = {"complain", "sell", "criticize", "reject", "hate", "terrible", "fail", "overpriced", "refuse", "lawsuit", "violation", "risk"}

def score_sentiment(text: str) -> float:
    """Score sentiment of text. Returns -1.0 to 1.0."""
    words = set(text.lower().split())
    pos = len(words & POSITIVE_KEYWORDS)
    neg = len(words & NEGATIVE_KEYWORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total

class SentimentTracker:
    """Tracks sentiment per agent over time."""
    def __init__(self, max_history_per_agent: int = 200):
        self._history: Dict[str, List[Tuple[float, float]]] = defaultdict(list) # agent_id -> [(timestamp, score)]
        self._max_history_per_agent = max_history_per_agent
    def record(self, agent_id: str, text: str, timestamp: float):
        score = score_sentiment(text)
        self._history[agent_id].append((timestamp, score))
        # Prune history if it exceeds max size
        if len(self._history[agent_id]) > self._max_history_per_agent:
            self._history[agent_id] = self._history[agent_id][-self._max_history_per_agent:]
    def record_action(self, agent_id: str, action: str, outcome_text: str, timestamp: float):
        combined = f"{action} {outcome_text}"
        self.record(agent_id, combined, timestamp)
    def get_sentiment(self, agent_id: str, window: int = 10) -> float:
        """Get average sentiment for agent over last N entries."""
        entries = self._history.get(agent_id, [])
        if not entries:
            return 0.0
        recent = entries[-window:]
        return sum(s for _, s in recent) / len(recent)
    def get_trend(self, agent_id: str, window: int = 10) -> str:
        """Get sentiment trend: rising, falling, stable."""
        entries = self._history.get(agent_id, [])
        if len(entries) < 4:
            return "stable"
        half = len(entries[-window:]) // 2
        recent = entries[-window:]
        first_half = sum(s for _, s in recent[:half]) / max(half, 1)
        second_half = sum(s for _, s in recent[half:]) / max(len(recent) - half, 1)
        diff = second_half - first_half
        if diff > 0.15:
            return "rising"
        elif diff < -0.15:
            return "falling"
        return "stable"
    def get_all_sentiments(self) -> Dict[str, float]:
        return {aid: self.get_sentiment(aid) for aid in self._history}
    def get_history(self, agent_id: str) -> List[Tuple[float, float]]:
        return self._history.get(agent_id, [])
