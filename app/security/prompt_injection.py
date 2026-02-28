from __future__ import annotations

import re
from dataclasses import dataclass


class PromptInjectionError(ValueError):
    pass


@dataclass(frozen=True)
class PromptInjectionDetection:
    suspicious: bool
    matches: list[str]


PROMPT_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bignore (all|any|previous|prior) instructions\b", re.IGNORECASE),
    re.compile(r"\bdisregard (the )?(system|developer|policy) prompt\b", re.IGNORECASE),
    re.compile(r"\breveal (the )?(system|developer) prompt\b", re.IGNORECASE),
    re.compile(r"\byou are now\b", re.IGNORECASE),
    re.compile(r"\bact as\b", re.IGNORECASE),
    re.compile(r"<\s*script\b", re.IGNORECASE),
)


def detect_prompt_injection(text: str) -> PromptInjectionDetection:
    matches: list[str] = []
    for pattern in PROMPT_INJECTION_PATTERNS:
        found = pattern.search(text)
        if found is not None:
            matches.append(found.group(0))
    return PromptInjectionDetection(suspicious=bool(matches), matches=matches)


def assert_no_prompt_injection(text: str, source: str) -> None:
    detection = detect_prompt_injection(text)
    if detection.suspicious:
        raise PromptInjectionError(
            f"prompt-injection signature detected in {source}: {', '.join(sorted(set(detection.matches)))}"
        )
