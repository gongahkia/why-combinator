#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import threading
import time
import uuid
from dataclasses import dataclass, field

import redis


def _checkpoint_run_lock_key(run_id: str) -> str:
    return f"lock:checkpoint-score:{run_id}"


@dataclass
class LoadStats:
    attempts: int = 0
    acquired: int = 0
    contended: int = 0
    errors: int = 0
    by_run: dict[str, dict[str, int]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, run_id: str, result: str) -> None:
        with self._lock:
            self.attempts += 1
            bucket = self.by_run.setdefault(run_id, {"attempts": 0, "acquired": 0, "contended": 0, "errors": 0})
            bucket["attempts"] += 1
            if result == "acquired":
                self.acquired += 1
                bucket["acquired"] += 1
            elif result == "contended":
                self.contended += 1
                bucket["contended"] += 1
            else:
                self.errors += 1
                bucket["errors"] += 1

    def summary(self, duration_seconds: float) -> dict[str, object]:
        contention_rate = (self.contended / self.attempts) if self.attempts else 0.0
        acquisition_rate = (self.acquired / self.attempts) if self.attempts else 0.0
        return {
            "duration_seconds": round(duration_seconds, 3),
            "attempts": self.attempts,
            "acquired": self.acquired,
            "contended": self.contended,
            "errors": self.errors,
            "acquisition_rate": round(acquisition_rate, 4),
            "contention_rate": round(contention_rate, 4),
            "by_run": self.by_run,
        }


def run_load_test(
    *,
    redis_url: str,
    run_count: int,
    worker_count: int,
    duration_seconds: int,
    checkpoint_interval_seconds: float,
    lock_timeout_seconds: int,
    simulated_score_seconds: float,
) -> dict[str, object]:
    run_ids = [str(uuid.uuid4()) for _ in range(run_count)]
    redis_client = redis.from_url(redis_url, decode_responses=True)
    stats = LoadStats()
    schedule_lock = threading.Lock()
    next_due: dict[str, float] = {run_id: time.monotonic() for run_id in run_ids}
    stop_at = time.monotonic() + duration_seconds

    for run_id in run_ids:
        redis_client.delete(_checkpoint_run_lock_key(run_id))

    def worker() -> None:
        while time.monotonic() < stop_at:
            run_id = random.choice(run_ids)
            now = time.monotonic()
            with schedule_lock:
                due = next_due[run_id]
                if now < due:
                    continue
                next_due[run_id] = now + checkpoint_interval_seconds

            lock = redis_client.lock(_checkpoint_run_lock_key(run_id), timeout=lock_timeout_seconds, blocking=False)
            try:
                if not lock.acquire(blocking=False):
                    stats.record(run_id, "contended")
                    time.sleep(0.002)
                    continue
                stats.record(run_id, "acquired")
                time.sleep(simulated_score_seconds)
            except Exception:
                stats.record(run_id, "errors")
            finally:
                try:
                    lock.release()
                except Exception:
                    pass

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(worker_count)]
    started_at = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=max(duration_seconds + 1, 1))
    finished_at = time.monotonic()
    redis_client.close()
    return stats.summary(finished_at - started_at)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load test for checkpoint lock contention in Redis.")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--run-count", type=int, default=50)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--duration-seconds", type=int, default=30)
    parser.add_argument("--checkpoint-interval-seconds", type=float, default=0.1)
    parser.add_argument("--lock-timeout-seconds", type=int, default=2)
    parser.add_argument("--simulated-score-seconds", type=float, default=0.03)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_load_test(
        redis_url=args.redis_url,
        run_count=args.run_count,
        worker_count=args.workers,
        duration_seconds=args.duration_seconds,
        checkpoint_interval_seconds=args.checkpoint_interval_seconds,
        lock_timeout_seconds=args.lock_timeout_seconds,
        simulated_score_seconds=args.simulated_score_seconds,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
