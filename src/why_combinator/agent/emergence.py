"""Emergent behavior detection - flags unusual patterns in agent actions."""
import logging
from typing import List, Dict, Any, Optional
from collections import Counter
from why_combinator.models import InteractionLog

logger = logging.getLogger(__name__)

class EmergenceDetector:
    """Detects and flags emergent/unusual behavior patterns."""
    def __init__(self, window_size: int = 20, anomaly_threshold: float = 2.0):
        self.window_size = window_size
        self.anomaly_threshold = anomaly_threshold
        self.action_history: List[str] = []
        self.flags: List[Dict[str, Any]] = []
    def observe(self, interaction: InteractionLog):
        """Feed an interaction to the detector."""
        self.action_history.append(interaction.action)
        if len(self.action_history) >= self.window_size:
            self._check_patterns()
    def _check_patterns(self):
        recent = self.action_history[-self.window_size:]
        counts = Counter(recent)
        total = len(recent)
        for action, count in counts.items(): # detect action dominance
            ratio = count / total
            if ratio > 0.6:
                self._flag("action_dominance", f"Action '{action}' dominates at {ratio:.0%} of recent actions", severity="warning")
        unique_ratio = len(counts) / total # detect sudden diversity collapse
        if unique_ratio < 0.15:
            self._flag("diversity_collapse", f"Only {len(counts)} unique actions in last {self.window_size} steps", severity="warning")
        if len(self.action_history) >= self.window_size * 2: # detect sudden behavior shift
            prev = Counter(self.action_history[-self.window_size*2:-self.window_size])
            curr = Counter(recent)
            prev_top = prev.most_common(1)[0][0] if prev else None
            curr_top = curr.most_common(1)[0][0] if curr else None
            if prev_top and curr_top and prev_top != curr_top:
                prev_ratio = prev.get(curr_top, 0) / max(sum(prev.values()), 1)
                curr_ratio = curr[curr_top] / total
                if curr_ratio > prev_ratio * self.anomaly_threshold:
                    self._flag("behavior_shift", f"Shift from '{prev_top}' to '{curr_top}' (was {prev_ratio:.0%}, now {curr_ratio:.0%})", severity="info")
    def _flag(self, flag_type: str, description: str, severity: str = "info"):
        flag = {"type": flag_type, "description": description, "severity": severity, "tick": len(self.action_history)}
        if not self.flags or self.flags[-1].get("type") != flag_type: # avoid duplicate consecutive flags
            self.flags.append(flag)
            logger.info(f"Emergence flag [{severity}]: {description}")
    def get_flags(self, since_tick: int = 0) -> List[Dict[str, Any]]:
        return [f for f in self.flags if f["tick"] >= since_tick]
    def reset(self):
        self.action_history.clear()
        self.flags.clear()
