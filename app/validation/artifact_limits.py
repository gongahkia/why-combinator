from __future__ import annotations

import os


class ArtifactLimitError(ValueError):
    pass


def load_max_artifacts_per_submission() -> int:
    return int(os.getenv("MAX_ARTIFACTS_PER_SUBMISSION", "25"))


def load_max_total_artifact_bytes_per_submission() -> int:
    return int(os.getenv("MAX_TOTAL_ARTIFACT_BYTES_PER_SUBMISSION", str(50 * 1024 * 1024)))


def validate_artifact_submission_limits(
    *,
    existing_count: int,
    existing_total_bytes: int,
    incoming_sizes: list[int],
) -> None:
    max_count = max(1, load_max_artifacts_per_submission())
    max_total_bytes = max(1, load_max_total_artifact_bytes_per_submission())

    projected_count = existing_count + len(incoming_sizes)
    if projected_count > max_count:
        raise ArtifactLimitError(
            f"artifact count limit exceeded: projected={projected_count}, allowed={max_count}"
        )

    projected_total = existing_total_bytes + sum(max(0, size) for size in incoming_sizes)
    if projected_total > max_total_bytes:
        raise ArtifactLimitError(
            f"artifact total size limit exceeded: projected={projected_total} bytes, allowed={max_total_bytes} bytes"
        )
