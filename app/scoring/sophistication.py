from __future__ import annotations

from dataclasses import dataclass

from app.db.enums import ArtifactType
from app.orchestrator.policy import resolve_artifact_sophistication_policy


@dataclass(frozen=True)
class ArtifactSophisticationRubricResult:
    rubric_score: float
    actual_sophistication: float
    expected_sophistication: float
    tolerance: float


_ARTIFACT_SOPHISTICATION_WEIGHTS: dict[ArtifactType, float] = {
    ArtifactType.CLI_PACKAGE: 0.35,
    ArtifactType.NOTEBOOK: 0.45,
    ArtifactType.WEB_BUNDLE: 0.65,
    ArtifactType.API_SERVICE: 0.75,
}


def _actual_sophistication(artifact_types: list[ArtifactType]) -> float:
    if not artifact_types:
        return 0.0
    base = sum(_ARTIFACT_SOPHISTICATION_WEIGHTS.get(artifact_type, 0.35) for artifact_type in artifact_types) / len(
        artifact_types
    )
    diversity_bonus = min(0.2, max(0, len(set(artifact_types)) - 1) * 0.05)
    return round(min(1.0, base + diversity_bonus), 6)


def evaluate_artifact_sophistication_rubric(
    artifact_types: list[ArtifactType],
    complexity_slider: float,
) -> ArtifactSophisticationRubricResult:
    policy = resolve_artifact_sophistication_policy(complexity_slider)
    actual = _actual_sophistication(artifact_types)
    deviation = abs(actual - policy.target_sophistication)
    denominator = max(0.1, policy.tolerance * 2.0)
    rubric_score = round(max(0.0, min(1.0, 1.0 - (deviation / denominator))), 6)
    return ArtifactSophisticationRubricResult(
        rubric_score=rubric_score,
        actual_sophistication=actual,
        expected_sophistication=policy.target_sophistication,
        tolerance=policy.tolerance,
    )
