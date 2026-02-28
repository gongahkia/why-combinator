from __future__ import annotations

import hashlib
import re
from typing import Iterable

from app.integrations.codex_client import CodexClient, CodexClientError, CodexRequest

SUMMARY_TEMPERATURE = 0.0
SUMMARY_MAX_OUTPUT_TOKENS = 180


def build_submission_summary_prompt(
    *,
    challenge_prompt: str,
    value_hypothesis: str,
    artifact_descriptors: Iterable[str] | None = None,
) -> str:
    artifacts_text = ", ".join(artifact_descriptors or [])
    return (
        "You generate semantic summaries for hackathon submissions.\n"
        "Write exactly 2 concise sentences describing the core idea, execution approach, and user value.\n"
        "Do not include bullet points or markdown.\n"
        f"Challenge prompt: {challenge_prompt}\n"
        f"Value hypothesis: {value_hypothesis}\n"
        f"Artifacts: {artifacts_text or 'none'}\n"
        "Summary:"
    )


def generate_submission_semantic_summary(
    *,
    challenge_prompt: str,
    value_hypothesis: str,
    artifact_descriptors: Iterable[str] | None = None,
) -> str:
    prompt = build_submission_summary_prompt(
        challenge_prompt=challenge_prompt,
        value_hypothesis=value_hypothesis,
        artifact_descriptors=artifact_descriptors,
    )
    client = CodexClient(max_retries=2, backoff_base_seconds=0.4)
    try:
        response = client.call(
            CodexRequest(
                prompt=prompt,
                temperature=SUMMARY_TEMPERATURE,
                max_output_tokens=SUMMARY_MAX_OUTPUT_TOKENS,
            )
        )
        cleaned = _normalize_summary(response.text)
        if len(cleaned) >= 10:
            return cleaned
    except CodexClientError:
        pass
    return _fallback_summary(challenge_prompt, value_hypothesis, artifact_descriptors)


def _normalize_summary(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if len(cleaned) > 500:
        return cleaned[:497].rstrip() + "..."
    return cleaned


def _fallback_summary(
    challenge_prompt: str,
    value_hypothesis: str,
    artifact_descriptors: Iterable[str] | None,
) -> str:
    challenge_compact = _truncate(_squash(challenge_prompt), 100)
    hypothesis_compact = _truncate(_squash(value_hypothesis), 240)
    artifact_list = list(artifact_descriptors or [])
    artifact_phrase = (
        f" Artifacts include {', '.join(_truncate(item, 32) for item in artifact_list[:3])}."
        if artifact_list
        else ""
    )
    digest = hashlib.sha256(f"{challenge_compact}|{hypothesis_compact}".encode("utf-8")).hexdigest()[:8]
    return (
        f"Submission for challenge '{challenge_compact}' proposes: {hypothesis_compact}.{artifact_phrase} "
        f"Deterministic fallback id {digest}."
    )


def _squash(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value: str, size: int) -> str:
    if len(value) <= size:
        return value
    return value[: size - 3].rstrip() + "..."
