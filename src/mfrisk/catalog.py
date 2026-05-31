"""Catalog: build the canonical fund universe from AMFI + mfapi.

Pure, network-light (one AMFI file + one mfapi list). Produces:
  - funds.json     : canonical Growth funds (Direct/Regular grouped), classified
  - worklist.json  : scheme codes in priority order (the full ingest plan)
  - sample_1k.json : stratified 1,000-fund slice across all asset classes
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import httpx

from .priority import PRIORITY_SEQUENCE, rank

AMFI_NAVALL = "https://portal.amfiindia.com/spages/NAVAll.txt"
MFAPI_LIST = "https://api.mfapi.in/mf"

_DEBT_KW = (
    "sdl", "gilt", "g-sec", "g sec", "gsec", "treasury", "bond", "psu", "liquid",
    "duration", "overnight", "money market", "crisil ibx", "aaa", "t-bill", "tbill",
    "corporate debt", "credit",
)
_GLOBAL_KW = (
    "nasdaq", "s&p", "china", "japan", "us ", "u.s", "global", "world", "hang seng",
    "emerging", "developed", "greater china", "offshore", "overseas",
)
_OPTION_TOKENS = re.compile(
    r"\b(direct|regular|growth|idcw|dividend|bonus|plan|option|payout|"
    r"reinvest(ment)?|retail|institutional)\b"
)


def asset_class(category: str, name: str) -> str:
    """Map a SEBI category + scheme name to one of the priority asset classes."""
    c = (category or "").lower()
    n = (name or "").lower()
    if "equity scheme" in c:
        return "equity_global" if any(k in n for k in _GLOBAL_KW) else "equity_domestic"
    if "hybrid scheme" in c:
        if "arbitrage" in c:
            return "hybrid_arbitrage"
        if "multi asset" in c:
            return "hybrid_multiasset"
        return "hybrid"
    if "solution oriented" in c:
        return "solution"
    if "fof overseas" in c:
        return "equity_global"
    if "gold etf" in c or "silver" in n:
        return "commodity"
    if "debt scheme" in c or "gilt" in c or "money market" in c or c == "income":
        return "debt"
    if "index funds" in c or "fof domestic" in c or "etfs" in c:
        if any(k in n for k in _DEBT_KW):
            return "debt"
        if any(k in n for k in ("gold", "silver", "commodity")):
            return "commodity"
        return "equity_passive"
    if "close ended" in c or "interval" in c:
        return "debt" if ("income" in c or any(k in n for k in _DEBT_KW)) else "equity_domestic"
    return "other"


def is_growth(name: str) -> bool:
    """Canonical option = Growth, excluding IDCW/dividend/bonus payout variants."""
    n = name.lower()
    return "growth" in n and not any(
        k in n for k in ("idcw", "dividend", "bonus", "payout", "reinvest")
    )


def is_direct(name: str) -> bool:
    return "direct" in name.lower()


def base_name(name: str) -> str:
    """Strip plan/option tokens so Direct & Regular collapse to one fund key."""
    n = _OPTION_TOKENS.sub(" ", name.lower())
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def parse_amfi(text: str) -> list[dict]:
    """Parse AMFI NAVAll.txt into rows with their SEBI category header."""
    rows: list[dict] = []
    category = None
    house = None
    for ln in text.splitlines():
        if ";" not in ln:
            s = ln.strip()
            if not s:
                continue
            if s.endswith(")") and "(" in s:
                m = re.search(r"\((.*)\)", s)
                category = m.group(1) if m else s
            elif s.endswith("Mutual Fund"):
                house = s
            continue
        p = ln.split(";")
        if len(p) >= 6 and p[0].strip().isdigit():
            rows.append({
                "scheme_code": int(p[0]),
                "isin": p[1].strip() or None,
                "scheme_name": p[3].strip(),
                "category": category,
                "fund_house": house,
            })
    return rows


def _load_text(url: str, local: Path | None) -> str:
    if local and local.exists():
        return local.read_text(encoding="utf-8", errors="replace")
    return httpx.get(url, follow_redirects=True, timeout=90).text


def build(
    out_dir: Path,
    navall_local: Path | None = None,
    mflist_local: Path | None = None,
    sample_size: int = 1000,
) -> dict:
    """Build funds/worklist/sample artifacts. Returns a summary dict."""
    out_dir.mkdir(parents=True, exist_ok=True)
    amfi_rows = parse_amfi(_load_text(AMFI_NAVALL, navall_local))

    # group Direct/Regular Growth codes into one canonical fund
    funds: dict[tuple[str, str], dict] = {}
    for r in amfi_rows:
        if not is_growth(r["scheme_name"]):
            continue
        ac = asset_class(r["category"], r["scheme_name"])
        key = (ac, base_name(r["scheme_name"]))
        f = funds.setdefault(key, {
            "fund_id": None, "asset_class": ac, "display_name": r["scheme_name"],
            "fund_house": r["fund_house"], "category": r["category"],
            "direct_growth_code": None, "regular_growth_code": None,
        })
        if is_direct(r["scheme_name"]):
            f["direct_growth_code"] = r["scheme_code"]
        else:
            f["regular_growth_code"] = r["scheme_code"]
        # prefer the regular-plan name as display (longest history, stable)
        if not is_direct(r["scheme_name"]):
            f["display_name"] = r["scheme_name"]

    fund_list = []
    for i, ((ac, bn), f) in enumerate(sorted(funds.items())):
        f["fund_id"] = i
        f["base_name"] = bn
        fund_list.append(f)

    # worklist: every growth scheme code in priority order, fund-adjacent
    fund_list.sort(key=lambda f: (rank(f["asset_class"]), f["display_name"].lower()))
    worklist = []
    for f in fund_list:
        for code in (f["direct_growth_code"], f["regular_growth_code"]):
            if code:
                worklist.append({
                    "scheme_code": code, "fund_id": f["fund_id"],
                    "asset_class": f["asset_class"],
                })

    sample = _stratified_sample(fund_list, sample_size)

    (out_dir / "funds.json").write_text(json.dumps(fund_list, indent=0))
    (out_dir / "worklist.json").write_text(json.dumps(worklist, indent=0))
    (out_dir / "sample_1k.json").write_text(json.dumps(sample, indent=0))

    by_ac = defaultdict(int)
    for f in fund_list:
        by_ac[f["asset_class"]] += 1
    return {
        "funds": len(fund_list),
        "scheme_codes": len(worklist),
        "sample": len(sample),
        "by_asset_class": {ac: by_ac[ac] for ac in PRIORITY_SEQUENCE},
    }


def _stratified_sample(fund_list: list[dict], size: int) -> list[dict]:
    """Proportional-with-floor sample, evenly spaced by name within each class."""
    by_ac: dict[str, list[dict]] = defaultdict(list)
    for f in fund_list:
        by_ac[f["asset_class"]].append(f)
    total = len(fund_list)
    floor = 20
    quota: dict[str, int] = {}
    for ac, fs in by_ac.items():
        want = max(floor, round(size * len(fs) / total))
        quota[ac] = min(want, len(fs))
    # renormalize to hit `size` as closely as possible
    scale = size / max(1, sum(quota.values()))
    sample: list[dict] = []
    for ac in PRIORITY_SEQUENCE:
        fs = sorted(by_ac.get(ac, []), key=lambda f: f["display_name"].lower())
        if not fs:
            continue
        take = min(len(fs), max(1, round(quota[ac] * scale)))
        step = max(1, len(fs) // take)
        picked = fs[::step][:take]
        sample.extend(picked)
    return sample
