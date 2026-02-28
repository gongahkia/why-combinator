from __future__ import annotations

import subprocess


class URLFetchError(RuntimeError):
    pass



def fetch_url_content(url: str, timeout_seconds: int = 10, max_bytes: int = 1024 * 1024) -> bytes:
    connect_timeout_seconds = max(1, min(timeout_seconds, 5))
    read_timeout_seconds = max(1, timeout_seconds)
    max_redirects = 5
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
        url,
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout_seconds + 1)
    if result.returncode != 0:
        raise URLFetchError(result.stderr.decode("utf-8", errors="replace").strip() or "curl failed")
    if len(result.stdout) > max_bytes:
        raise URLFetchError(f"response exceeds size limit ({max_bytes} bytes)")
    return result.stdout
