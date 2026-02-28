from __future__ import annotations

import os


def load_novelty_floor() -> float:
    return float(os.getenv("NOVELTY_SCORE_FLOOR", "0.1"))


def normalize_novelty_score(raw_novelty_score: float, floor: float | None = None) -> float:
    novelty_floor = load_novelty_floor() if floor is None else floor
    bounded = max(0.0, min(1.0, raw_novelty_score))
    return round(max(novelty_floor, bounded), 6)
