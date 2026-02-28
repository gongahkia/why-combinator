from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status


async def enforce_token_bucket(
    request: Request,
    bucket_scope: str,
    capacity: int = 20,
    refill_per_second: float = 1.0,
) -> None:
    identity = request.headers.get("X-Api-Key") or (request.client.host if request.client else "anonymous")
    key = f"rate:{bucket_scope}:{identity}"
    now_ms = int(request.state.request_time_ms if hasattr(request.state, "request_time_ms") else 0)
    if now_ms == 0:
        from time import time

        now_ms = int(time() * 1000)

    script = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])
local state = redis.call('HMGET', key, 'tokens', 'last_ms')
local tokens = tonumber(state[1])
local last_ms = tonumber(state[2])
if tokens == nil then
  tokens = capacity
  last_ms = now_ms
end
local elapsed = math.max(0, now_ms - last_ms) / 1000.0
tokens = math.min(capacity, tokens + (elapsed * refill_rate))
if tokens < 1.0 then
  redis.call('HMSET', key, 'tokens', tokens, 'last_ms', now_ms)
  redis.call('PEXPIRE', key, 600000)
  return 0
end
tokens = tokens - 1.0
redis.call('HMSET', key, 'tokens', tokens, 'last_ms', now_ms)
redis.call('PEXPIRE', key, 600000)
return 1
"""
    allowed = int(await request.app.state.redis.eval(script, 1, key, now_ms, capacity, refill_per_second))
    if allowed != 1:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limit exceeded")


def rate_limit_dependency(bucket_scope: str, capacity: int = 20, refill_per_second: float = 1.0):
    async def _dependency(request: Request) -> None:
        await enforce_token_bucket(
            request=request,
            bucket_scope=bucket_scope,
            capacity=capacity,
            refill_per_second=refill_per_second,
        )

    return Depends(_dependency)
