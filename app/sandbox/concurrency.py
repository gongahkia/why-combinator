from __future__ import annotations

import os

import redis


def load_run_hacker_container_limit() -> int:
    return int(os.getenv("RUN_MAX_ACTIVE_HACKER_CONTAINERS", "4"))


def run_hacker_container_slot_key(run_id: str) -> str:
    return f"run:{run_id}:active_hacker_containers"


def acquire_run_hacker_container_slot(redis_client: redis.Redis, run_id: str, limit: int | None = None) -> tuple[bool, int]:
    hard_limit = max(1, limit if limit is not None else load_run_hacker_container_limit())
    script = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local current = tonumber(redis.call('GET', key) or '0')
if current >= limit then
  return -1
end
return redis.call('INCR', key)
"""
    result = int(redis_client.eval(script, 1, run_hacker_container_slot_key(run_id), hard_limit))
    if result == -1:
        current = int(redis_client.get(run_hacker_container_slot_key(run_id)) or "0")
        return False, max(hard_limit - current, 0)
    return True, max(hard_limit - result, 0)


def release_run_hacker_container_slot(redis_client: redis.Redis, run_id: str) -> None:
    script = """
local key = KEYS[1]
local current = tonumber(redis.call('GET', key) or '0')
if current <= 1 then
  redis.call('DEL', key)
  return 0
end
return redis.call('DECR', key)
"""
    redis_client.eval(script, 1, run_hacker_container_slot_key(run_id))
