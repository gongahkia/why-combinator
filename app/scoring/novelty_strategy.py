from __future__ import annotations

from typing import Literal


NoveltyStrategyMode = Literal["embedding_only", "hybrid_overlap"]


def resolve_novelty_strategy_mode(raw_value: str | None) -> NoveltyStrategyMode:
    normalized = (raw_value or "").strip().lower()
    if normalized == "hybrid_overlap":
        return "hybrid_overlap"
    return "embedding_only"


def select_similarity_penalty(
    strategy_mode: NoveltyStrategyMode,
    *,
    embedding_similarity_penalty: float,
    artifact_overlap_penalty: float,
) -> float:
    if strategy_mode == "hybrid_overlap":
        return max(embedding_similarity_penalty, artifact_overlap_penalty)
    return embedding_similarity_penalty
