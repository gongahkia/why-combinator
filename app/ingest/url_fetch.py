from __future__ import annotations

import subprocess

from app.ingest.sanitize import URLSanitizationError, sanitize_ingestion_url


class URLFetchError(RuntimeError):
    pass



def _resolve_effective_url(
    url: str,
    *,
    connect_timeout_seconds: int,
    read_timeout_seconds: int,
    max_redirects: int,
) -> str:
    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--fail",
        "--location",
        "--proto",
        "=http,https",
        "--connect-timeout",
        str(connect_timeout_seconds),
        "--max-time",
        str(read_timeout_seconds),
        "--max-redirs",
        str(max_redirects),
        "--output",
        "/dev/null",
        "--write-out",
        "%{url_effective}",
        url,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=read_timeout_seconds + 1)
    if result.returncode != 0:
        raise URLFetchError(result.stderr.decode("utf-8", errors="replace").strip() or "curl failed")
    effective_url = result.stdout.decode("utf-8", errors="replace").strip()
    return effective_url or url


def fetch_url_content(url: str, timeout_seconds: int = 10, max_bytes: int = 1024 * 1024) -> bytes:
    connect_timeout_seconds = max(1, min(timeout_seconds, 5))
    read_timeout_seconds = max(1, timeout_seconds)
    max_redirects = 5
    effective_url = _resolve_effective_url(
        url,
        connect_timeout_seconds=connect_timeout_seconds,
        read_timeout_seconds=read_timeout_seconds,
        max_redirects=max_redirects,
    )
    try:
        sanitize_ingestion_url(effective_url)
    except URLSanitizationError as exc:
        raise URLFetchError(f"redirect blocked by URL sanitization: {exc}") from exc

    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--fail",
        "--location",
        "--proto",
        "=http,https",
        "--connect-timeout",
        str(connect_timeout_seconds),
        "--max-time",
        str(read_timeout_seconds),
        "--max-redirs",
        str(max_redirects),
        "--max-filesize",
        str(max_bytes),
        effective_url,
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout_seconds + 1)
    if result.returncode != 0:
        raise URLFetchError(result.stderr.decode("utf-8", errors="replace").strip() or "curl failed")
    if len(result.stdout) > max_bytes:
        raise URLFetchError(f"response exceeds size limit ({max_bytes} bytes)")
    return result.stdout
