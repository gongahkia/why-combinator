from __future__ import annotations

import re


class PromptSafetyError(ValueError):
    pass


DISALLOWED_INTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(malware|ransomware|trojan|worm)\b", re.IGNORECASE),
    re.compile(r"\b(exploit|zero-day|privilege escalation)\b", re.IGNORECASE),
    re.compile(r"\b(phishing|credential theft|password spraying)\b", re.IGNORECASE),
    re.compile(r"\b(ddos|botnet|command and control|c2)\b", re.IGNORECASE),
    re.compile(r"\b(data exfiltration|unauthorized access)\b", re.IGNORECASE),
)


def validate_challenge_prompt_safety(prompt: str) -> None:
    for pattern in DISALLOWED_INTENT_PATTERNS:
        match = pattern.search(prompt)
        if match is not None:
            raise PromptSafetyError(f"disallowed execution intent detected: '{match.group(0)}'")
