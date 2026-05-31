"""Metrics engine — compute risk-adjusted stats per fund × window into DuckDB.

Convention (locked): month-end NAV returns, MAR = risk-free rate (default 6%).
Plan resolution: Direct-Growth for windows <= 10Y (fallback Regular), Regular-Growth
for 20Y. Ulcer Index / max drawdown use the daily series within the window.

Numerics are polars (no numpy/pandas).
"""

from __future__ import annotations

import gzip
import json
import math
from datetime import date, timedelta
from pathlib import Path

import duckdb
import polars as pl

RFR = 0.06  # annual risk-free rate
WINDOWS: list[tuple[str, float]] = [
    ("3m", 0.25), ("1Y", 1), ("3Y", 3), ("5Y", 5), ("7Y", 7), ("10Y", 10), ("20Y", 20),
]

CACHE_DIR = Path("data/cache")
CATALOG_DIR = Path("data/catalog")
DB_PATH = Path("data/mfrisk.db")


def load_series(code: int | None) -> pl.DataFrame | None:
    """Load a scheme's daily NAV as an ascending (date, nav) polars frame."""
    if not code:
        return None
    path = CACHE_DIR / f"{code}.json.gz"
    if not path.exists():
        return None
    payload = json.loads(gzip.decompress(path.read_bytes()))
    rows = payload.get("data")
    if payload.get("status") != "SUCCESS" or not rows:
        return None
    df = (
        pl.DataFrame({"date": [r["date"] for r in rows], "nav": [r["nav"] for r in rows]})
        .with_columns(
            pl.col("date").str.strptime(pl.Date, "%d-%m-%Y", strict=False),
            pl.col("nav").cast(pl.Float64, strict=False),
        )
        .drop_nulls()
        .filter(pl.col("nav") > 0)
        .sort("date")
    )
    if df.height < 2:
        return None
    # Drop data artifacts (face-value resets / scheme-code reuse / merges): no real
    # fund NAV moves >50% in a day. Keep the clean segment after the last such jump.
    df = df.with_columns(
        ((pl.col("nav") / pl.col("nav").shift(1) - 1).abs() > 0.5).alias("jump")
    ).with_row_index("i")
    bad = df.filter(pl.col("jump"))["i"]
    if bad.len():
        df = df.slice(int(bad[-1]) + 1)
    df = df.select("date", "nav")
    return df if df.height > 1 else None


def _span_days(df: pl.DataFrame) -> int:
    return (df["date"].max() - df["date"].min()).days


def _covers(df: pl.DataFrame, years: float) -> bool:
    return _span_days(df) >= years * 365.25 * 0.9


def pick_series(direct: pl.DataFrame | None, regular: pl.DataFrame | None, years: float):
    """Return (frame, plan_label) per the Direct<=10Y / Regular>10Y rule."""
    if years <= 10:
        if direct is not None and _covers(direct, years):
            return direct, "direct"
        if regular is not None and _covers(regular, years):
            return regular, "regular"
        if direct is not None:
            return direct, "direct"
        return (regular, "regular") if regular is not None else (None, None)
    if regular is not None:
        return regular, "regular"
    return (direct, "direct") if direct is not None else (None, None)


def window_metrics(df: pl.DataFrame, years: float) -> dict | None:
    """Compute the metric set for one series over one trailing window."""
    as_of = df["date"].max()
    start = as_of - timedelta(days=round(years * 365.25))
    daily = df.filter(pl.col("date") >= start)
    if daily.height < 3:
        return None

    monthly = (
        daily.group_by_dynamic("date", every="1mo").agg(pl.col("nav").last()).sort("date")
    )
    rets = monthly.select(r=pl.col("nav").pct_change()).drop_nulls()
    n = rets.height
    expected = max(2, round(years * 12))
    if n < max(2, math.floor(0.8 * expected)):
        return None

    k = 12
    mar_m = (1 + RFR) ** (1 / 12) - 1
    agg = rets.select(
        growth=(pl.col("r") + 1).product(),
        vol_m=pl.col("r").std(ddof=1),
        down_m=(pl.min_horizontal(pl.col("r") - mar_m, 0.0).pow(2).mean().sqrt()),
    ).row(0, named=True)

    ann_return = agg["growth"] ** (k / n) - 1
    vol = (agg["vol_m"] or 0.0) * math.sqrt(k)
    downside = (agg["down_m"] or 0.0) * math.sqrt(k)
    excess = ann_return - RFR
    sortino = excess / downside if downside > 1e-9 else None
    sharpe = excess / vol if vol > 1e-9 else None

    start_nav = float(monthly["nav"][0])
    end_nav = float(monthly["nav"][-1])
    yrs = n / 12
    cagr = (end_nav / start_nav) ** (1 / yrs) - 1 if start_nav > 0 else None

    dd = daily.select(
        dd=((pl.col("nav") / pl.col("nav").cum_max() - 1.0) * 100.0)
    ).select(
        ulcer=pl.col("dd").pow(2).mean().sqrt(),
        max_dd=pl.col("dd").min(),
    ).row(0, named=True)
    ulcer = dd["ulcer"]
    max_dd = dd["max_dd"] / 100.0
    martin = excess / ulcer if ulcer and ulcer > 1e-9 else None

    return {
        "n_months": n, "cagr": cagr, "ann_return": ann_return, "vol": vol,
        "downside_dev": downside, "sortino": sortino, "sharpe": sharpe,
        "max_drawdown": max_dd, "ulcer_index": ulcer, "martin": martin,
    }


def compute(progress_every: int = 250) -> dict:
    """Compute all funds × windows, write fund/metric/market_event to DuckDB."""
    funds = json.loads((CATALOG_DIR / "funds.json").read_text())
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    con.execute("""
        CREATE TABLE fund(
            fund_id INTEGER, display_name TEXT, fund_house TEXT, category TEXT,
            asset_class TEXT, direct_growth_code INTEGER, regular_growth_code INTEGER,
            as_of DATE, inactive BOOLEAN);
        CREATE TABLE metric(
            fund_id INTEGER, win TEXT, plan_used TEXT, as_of DATE, n_months INTEGER,
            cagr DOUBLE, ann_return DOUBLE, vol DOUBLE, downside_dev DOUBLE,
            sortino DOUBLE, sharpe DOUBLE, max_drawdown DOUBLE, ulcer_index DOUBLE,
            martin DOUBLE);
        CREATE TABLE market_event(date DATE, label TEXT, category TEXT, severity INTEGER, note TEXT);
    """)

    from .data.market_events import events as ev
    con.executemany("INSERT INTO market_event VALUES (?,?,?,?,?)",
                    [(e["date"], e["label"], e["category"], e["severity"], e["note"]) for e in ev()])

    today = date.today()
    fund_rows, metric_rows = [], []
    computed = 0
    for f in funds:
        direct = load_series(f["direct_growth_code"])
        regular = load_series(f["regular_growth_code"])
        if direct is None and regular is None:
            continue
        as_of = max(s["date"].max() for s in (direct, regular) if s is not None)
        inactive = (today - as_of).days > 45
        fund_rows.append((
            f["fund_id"], f["display_name"], f.get("fund_house"), f.get("category"),
            f["asset_class"], f["direct_growth_code"], f["regular_growth_code"],
            as_of, inactive,
        ))
        for wname, yrs in WINDOWS:
            s, plan = pick_series(direct, regular, yrs)
            if s is None:
                continue
            m = window_metrics(s, yrs)
            if not m:
                continue
            metric_rows.append((
                f["fund_id"], wname, plan, s["date"].max(), m["n_months"],
                m["cagr"], m["ann_return"], m["vol"], m["downside_dev"], m["sortino"],
                m["sharpe"], m["max_drawdown"], m["ulcer_index"], m["martin"],
            ))
        computed += 1
        if computed % progress_every == 0:
            print(f"  computed {computed}/{len(funds)} funds, {len(metric_rows)} metric rows",
                  flush=True)

    con.executemany("INSERT INTO fund VALUES (" + ",".join(["?"] * 9) + ")", fund_rows)
    con.executemany("INSERT INTO metric VALUES (" + ",".join(["?"] * 14) + ")", metric_rows)
    con.execute("CREATE INDEX idx_metric_window ON metric(win)")
    con.execute("CREATE INDEX idx_fund_ac ON fund(asset_class)")
    con.close()
    return {"funds": len(fund_rows), "metric_rows": len(metric_rows)}
