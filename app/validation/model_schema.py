from __future__ import annotations

import json
from dataclasses import dataclass


class ModelResponseValidationError(ValueError):
    pass


@dataclass(frozen=True)
class JudgeModelResponse:
    score: float
    rationale: str
    confidence: float | None = None


@dataclass(frozen=True)
class HackerModelResponse:
    summary: str
    value_hypothesis: str
    artifacts: list[str]


def _load_json_object(text: str) -> dict[str, object]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelResponseValidationError(f"response is not valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ModelResponseValidationError("response must be a JSON object")
    return payload


def validate_judge_response_json(text: str) -> JudgeModelResponse:
    payload = _load_json_object(text)
    allowed_keys = {"score", "rationale", "confidence"}
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        raise ModelResponseValidationError(f"unexpected judge response keys: {sorted(unknown_keys)}")
    if "score" not in payload or "rationale" not in payload:
        raise ModelResponseValidationError("judge response requires score and rationale")

    score_value = payload["score"]
    rationale_value = payload["rationale"]
    if not isinstance(score_value, (int, float)):
        raise ModelResponseValidationError("judge score must be numeric")
    score = float(score_value)
    if score < 0.0 or score > 1.0:
        raise ModelResponseValidationError("judge score must be between 0 and 1")
    if not isinstance(rationale_value, str) or not rationale_value.strip():
        raise ModelResponseValidationError("judge rationale must be a non-empty string")

    confidence: float | None = None
    confidence_value = payload.get("confidence")
    if confidence_value is not None:
        if not isinstance(confidence_value, (int, float)):
            raise ModelResponseValidationError("judge confidence must be numeric when provided")
        confidence = float(confidence_value)
        if confidence < 0.0 or confidence > 1.0:
            raise ModelResponseValidationError("judge confidence must be between 0 and 1")

    return JudgeModelResponse(score=round(score, 4), rationale=rationale_value.strip(), confidence=confidence)


def validate_hacker_response_json(text: str) -> HackerModelResponse:
    payload = _load_json_object(text)
    required = {"summary", "value_hypothesis", "artifacts"}
    unknown_keys = set(payload) - required
    if unknown_keys:
        raise ModelResponseValidationError(f"unexpected hacker response keys: {sorted(unknown_keys)}")
    missing = required - set(payload)
    if missing:
        raise ModelResponseValidationError(f"hacker response missing required keys: {sorted(missing)}")

    summary = payload["summary"]
    value_hypothesis = payload["value_hypothesis"]
    artifacts = payload["artifacts"]
    if not isinstance(summary, str) or len(summary.strip()) < 10:
        raise ModelResponseValidationError("hacker summary must be a non-empty string with length >= 10")
    if not isinstance(value_hypothesis, str) or len(value_hypothesis.strip()) < 10:
        raise ModelResponseValidationError("hacker value_hypothesis must be a non-empty string with length >= 10")
    if not isinstance(artifacts, list) or not artifacts:
        raise ModelResponseValidationError("hacker artifacts must be a non-empty array")
    if not all(isinstance(item, str) and item.strip() for item in artifacts):
        raise ModelResponseValidationError("hacker artifacts must contain non-empty strings")

    return HackerModelResponse(
        summary=summary.strip(),
        value_hypothesis=value_hypothesis.strip(),
        artifacts=[item.strip() for item in artifacts],
    )
