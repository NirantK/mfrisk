"""Async NAV-history fetcher — fast, polite, resumable.

Politeness contract (see docs/plans/2026-05-31-data-ingestion.md):
  - bounded concurrency (semaphore)
  - jittered spacing before each request
  - exponential backoff WITH full jitter on 429/5xx/timeouts (via tenacity)
  - resumable: a code whose cache file exists is skipped

Cache layout: ``<cache_dir>/<scheme_code>.json.gz`` holding the raw mfapi payload.
The cache IS the resumable store — both the 1K sample run and the background
full run append to it and skip what's already there.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import random
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

MFAPI = "https://api.mfapi.in/mf/{code}"


class Retryable(Exception):
    """Raised for transient HTTP conditions worth retrying."""


@retry(
    wait=wait_random_exponential(multiplier=0.5, max=30),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((Retryable, httpx.TransportError)),
    reraise=True,
)
async def _get(client: httpx.AsyncClient, code: int) -> dict:
    resp = await client.get(MFAPI.format(code=code))
    if resp.status_code == 429 or resp.status_code >= 500:
        raise Retryable(f"{resp.status_code} for {code}")
    resp.raise_for_status()
    return resp.json()


async def _fetch_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    code: int,
    cache_dir: Path,
    base_delay: float,
    jitter: float,
) -> str:
    path = cache_dir / f"{code}.json.gz"
    if path.exists() and path.stat().st_size > 0:
        return "skip"
    async with sem:
        await asyncio.sleep(base_delay + random.uniform(0, jitter))
        # network boundary: after tenacity exhausts its retries we don't crash the
        # whole run — a code that still fails is "error" and gets retried later.
        try:
            payload = await _get(client, code)
        except (httpx.HTTPError, Retryable):
            return "error"
    if payload.get("status") != "SUCCESS" or not payload.get("data"):
        path.write_bytes(gzip.compress(json.dumps({"status": "EMPTY"}).encode()))
        return "empty"
    path.write_bytes(gzip.compress(json.dumps(payload).encode()))
    return "ok"


async def run(
    codes: list[int],
    cache_dir: Path,
    concurrency: int = 8,
    base_delay: float = 0.15,
    jitter: float = 0.25,
    chunk: int = 500,
    stuck_streak_limit: int = 3,
) -> dict:
    """Fetch all codes into cache_dir, in chunks, resumably.

    Detects a rate-limit / outage "stuck" state: if `stuck_streak_limit`
    consecutive chunks come back >80% errors, stop cleanly (cache stays
    resumable) and return ``stuck=True`` so the caller can back off and retry
    later. Returns status counts.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(concurrency)
    counts = {"ok": 0, "empty": 0, "skip": 0, "error": 0, "stuck": False}
    done = 0
    stuck_streak = 0
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(
        http2=True, timeout=httpx.Timeout(connect=10, read=30, write=10, pool=30), limits=limits,
        headers={"User-Agent": "mfrisk/0.1 (+github.com/NirantK/mfrisk)"},
    ) as client:
        for start in range(0, len(codes), chunk):
            batch = codes[start:start + chunk]
            results = await asyncio.gather(
                *[_fetch_one(client, sem, c, cache_dir, base_delay, jitter) for c in batch]
            )
            for s in results:
                counts[s] += 1
            done += len(batch)
            fresh = [s for s in results if s != "skip"]
            err = sum(1 for s in fresh if s == "error")
            print(f"  {done}/{len(codes)}  ok={counts['ok']} empty={counts['empty']} "
                  f"skip={counts['skip']} error={counts['error']}", flush=True)
            if fresh and err / len(fresh) > 0.8:
                stuck_streak += 1
                if stuck_streak >= stuck_streak_limit:
                    counts["stuck"] = True
                    print(f"  STUCK after {stuck_streak} bad chunks — stopping; "
                          f"cache is resumable.", flush=True)
                    break
            else:
                stuck_streak = 0
    return counts
