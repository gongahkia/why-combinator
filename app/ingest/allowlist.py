from __future__ import annotations

import json
import os
import uuid
from urllib.parse import urlparse


class URLAllowlistError(ValueError):
    pass


def _load_allowlist_by_challenge() -> dict[str, list[str]]:
    raw = os.getenv("URL_INGEST_ALLOWLIST_BY_CHALLENGE_JSON", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise URLAllowlistError(f"invalid URL_INGEST_ALLOWLIST_BY_CHALLENGE_JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise URLAllowlistError("allowlist override must be a JSON object")

    normalized: dict[str, list[str]] = {}
    for challenge_id, domains in payload.items():
        if not isinstance(challenge_id, str):
            continue
        if not isinstance(domains, list):
            continue
        normalized[challenge_id] = [str(domain).strip().lower() for domain in domains if str(domain).strip()]
    return normalized


def _host_matches_allowlist(hostname: str, allowed_domains: list[str]) -> bool:
    for domain in allowed_domains:
        if hostname == domain or hostname.endswith(f".{domain}"):
            return True
    return False


def assert_url_allowed_for_challenge(challenge_id: uuid.UUID, url: str) -> None:
    allowlist_by_challenge = _load_allowlist_by_challenge()
    allowlist = allowlist_by_challenge.get(str(challenge_id), [])
    if not allowlist:
        return

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise URLAllowlistError("URL hostname is required for allowlist checks")
    if not _host_matches_allowlist(hostname, allowlist):
        raise URLAllowlistError(
            f"hostname '{hostname}' is not in challenge allowlist override for challenge {challenge_id}"
        )
