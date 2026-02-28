from __future__ import annotations

import subprocess


class URLFetchError(RuntimeError):
    pass



def fetch_url_content(url: str, timeout_seconds: int = 10, max_bytes: int = 1024 * 1024) -> bytes:
    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--location",
        "--max-time",
        str(timeout_seconds),
        url,
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout_seconds + 1)
    if result.returncode != 0:
        raise URLFetchError(result.stderr.decode("utf-8", errors="replace").strip() or "curl failed")
    if len(result.stdout) > max_bytes:
        raise URLFetchError(f"response exceeds size limit ({max_bytes} bytes)")
    return result.stdout
