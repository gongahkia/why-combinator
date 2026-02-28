from __future__ import annotations

import os

import redis


def create_redis_client() -> redis.Redis:
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


def run_budget_key(run_id: str) -> str:
    return f"run:{run_id}:budget_remaining"


def task_cost_from_env(task_name: str, default: int) -> int:
    env_key = f"{task_name.upper()}_TASK_BUDGET_COST"
    return int(os.getenv(env_key, str(default)))


def reserve_budget(redis_client: redis.Redis, run_id: str, units: int) -> tuple[bool, int | None]:
    script = """
local key = KEYS[1]
local cost = tonumber(ARGV[1])
local remaining = tonumber(redis.call('GET', key))
if remaining == nil then
  return -2
end
if remaining < cost then
  return -1
end
return redis.call('DECRBY', key, cost)
"""
    result = int(redis_client.eval(script, 1, run_budget_key(run_id), units))
    if result == -2:
        return False, None
    if result == -1:
        current = redis_client.get(run_budget_key(run_id))
        return False, int(current) if current is not None else None
    return True, result
