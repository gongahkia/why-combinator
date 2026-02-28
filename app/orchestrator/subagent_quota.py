from __future__ import annotations

import os

import redis


def subagent_quota_key(run_id: str, parent_agent_id: str) -> str:
    return f"run:{run_id}:agent:{parent_agent_id}:subagent_spawns_used"


def load_default_per_agent_quota() -> int:
    return int(os.getenv("SUBAGENT_SPAWN_QUOTA_PER_AGENT", "10"))


def check_and_reserve_subagent_quota(
    redis_client: redis.Redis,
    run_id: str,
    parent_agent_id: str,
    increment: int = 1,
    quota_limit: int | None = None,
) -> tuple[bool, int]:
    limit = quota_limit if quota_limit is not None else load_default_per_agent_quota()
    script = """
local key = KEYS[1]
local inc = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local used = tonumber(redis.call('GET', key) or '0')
if used + inc > limit then
  return -1
end
return redis.call('INCRBY', key, inc)
"""
    result = int(redis_client.eval(script, 1, subagent_quota_key(run_id, parent_agent_id), increment, limit))
    if result == -1:
        current_used = int(redis_client.get(subagent_quota_key(run_id, parent_agent_id)) or "0")
        return False, max(limit - current_used, 0)
    return True, max(limit - result, 0)
