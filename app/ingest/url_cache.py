from __future__ import annotations

import base64
import hashlib

from redis.asyncio import Redis

from app.ingest.url_fetch import fetch_url_content


def build_url_fetch_cache_key(url: str, timeout_seconds: int, max_bytes: int) -> str:
    raw = f"{url}|timeout={timeout_seconds}|max_bytes={max_bytes}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"url_fetch_cache:{digest}"


async def fetch_url_content_cached(
    redis_client: Redis,
    url: str,
    timeout_seconds: int,
    max_bytes: int,
    ttl_seconds: int = 300,
) -> bytes:
    key = build_url_fetch_cache_key(url=url, timeout_seconds=timeout_seconds, max_bytes=max_bytes)
    cached = await redis_client.get(key)
    if cached:
        return base64.b64decode(cached)

    content = fetch_url_content(url, timeout_seconds=timeout_seconds, max_bytes=max_bytes)
    await redis_client.set(key, base64.b64encode(content).decode("ascii"), ex=ttl_seconds)
    await redis_client.set(f"{key}:content_hash", hashlib.sha256(content).hexdigest(), ex=ttl_seconds)
    return content
