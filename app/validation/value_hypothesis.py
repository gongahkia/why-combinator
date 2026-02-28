from __future__ import annotations

import re


_ACTION_VERB_PATTERN = re.compile(
    r"\b(improve|increase|reduce|decrease|cut|grow|boost|raise|lower|minimize|maximize|shorten|speed up)\b",
    re.IGNORECASE,
)
_METRIC_PATTERN = re.compile(
    r"\b(latency|time|throughput|conversion|revenue|cost|error|uptime|retention|engagement|accuracy|quality|acknowledgment)\b",
    re.IGNORECASE,
)
_NUMERIC_TARGET_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|percent|x|ms|s|sec|seconds?|minutes?|hours?|days?|weeks?|months?|usd|\$)?\b",
    re.IGNORECASE,
)


def validate_measurable_value_hypothesis(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return ["value_hypothesis is required"]

    has_action = bool(_ACTION_VERB_PATTERN.search(normalized))
    has_metric = bool(_METRIC_PATTERN.search(normalized))
    has_numeric_target = bool(_NUMERIC_TARGET_PATTERN.search(normalized))
    if has_action and has_metric and has_numeric_target:
        return []
    return ["value_hypothesis must describe a measurable outcome (action + metric + numeric target)"]
