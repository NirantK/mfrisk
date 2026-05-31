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
        payload = await _get(client, code)
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
    progress_every: int = 200,
) -> dict:
    """Fetch all codes into cache_dir. Returns status counts."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(concurrency)
    counts = {"ok": 0, "empty": 0, "skip": 0}
    done = 0
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(
        http2=True, timeout=httpx.Timeout(connect=10, read=30, write=10, pool=30), limits=limits,
        headers={"User-Agent": "mfrisk/0.1 (+github.com/NirantK/mfrisk)"},
    ) as client:
        tasks = [
            _fetch_one(client, sem, c, cache_dir, base_delay, jitter) for c in codes
        ]
        for fut in asyncio.as_completed(tasks):
            status = await fut
            counts[status] += 1
            done += 1
            if done % progress_every == 0:
                print(f"  {done}/{len(codes)}  ok={counts['ok']} "
                      f"empty={counts['empty']} skip={counts['skip']}", flush=True)
    return counts
