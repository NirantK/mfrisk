"""FastAPI + HTMX microsite over the precomputed DuckDB metrics."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import duckdb
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..priority import PRIORITY_SEQUENCE

DB_PATH = Path("data/mfrisk.db")
CACHE_DIR = Path("data/cache")
BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="mfrisk")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

# metric column -> (label, lower_is_better)
METRICS = {
    "sortino": ("Sortino", False),
    "ulcer_index": ("Ulcer Index", True),
    "martin": ("Martin (UPI)", False),
    "cagr": ("CAGR", False),
    "ann_return": ("Ann. Return", False),
    "max_drawdown": ("Max Drawdown", False),
    "sharpe": ("Sharpe", False),
    "vol": ("Volatility", True),
}
WINDOWS = ["3m", "1Y", "3Y", "5Y", "7Y", "10Y", "20Y"]
ASSET_LABELS = {
    "equity_domestic": "Equity (India)", "equity_global": "Equity (Global)",
    "equity_passive": "Equity (Index/ETF)", "hybrid": "Hybrid",
    "hybrid_multiasset": "Multi-Asset", "hybrid_arbitrage": "Arbitrage",
    "solution": "Solution", "commodity": "Commodity", "debt": "Debt", "other": "Other",
}


def con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


def _rows(window: str, asset: str, q: str, sort: str, direction: str,
          limit: int, offset: int):
    # Convention: higher is better for every metric — uniform sort direction.
    primary = sort if sort in METRICS else "sortino"
    dir_sql = "DESC" if direction == "desc" else "ASC"
    order = f"m.{primary} {dir_sql} NULLS LAST"
    where = ["m.win = ?"]
    params: list = [window]
    if asset and asset != "all":
        where.append("f.asset_class = ?")
        params.append(asset)
    if q:
        where.append("LOWER(f.display_name) LIKE ?")
        params.append(f"%{q.lower()}%")
    sql = f"""
        SELECT f.fund_id, f.display_name, f.fund_house, f.asset_class, f.category,
               f.inactive, f.spark, m.plan_used, m.sortino, m.ulcer_index, m.martin, m.cagr,
               m.ann_return, m.max_drawdown, m.sharpe, m.vol, m.n_months
        FROM metric m JOIN fund f USING (fund_id)
        WHERE {' AND '.join(where)}
        ORDER BY {order}
        LIMIT ? OFFSET ?"""
    params += [limit, offset]
    with con() as c:
        cur = c.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with con() as c:
        nfunds = c.execute("SELECT COUNT(*) FROM fund").fetchone()[0]
        nmetrics = c.execute("SELECT COUNT(*) FROM metric").fetchone()[0]
        ac_counts = dict(c.execute(
            "SELECT asset_class, COUNT(*) FROM fund GROUP BY 1").fetchall())
    return templates.TemplateResponse(request, "index.html", {
        "metrics": METRICS, "windows": WINDOWS,
        "assets": [(a, ASSET_LABELS[a], ac_counts.get(a, 0)) for a in PRIORITY_SEQUENCE],
        "nfunds": nfunds, "nmetrics": nmetrics,
    })


@app.get("/rank", response_class=HTMLResponse)
def rank(request: Request, window: str = "3Y", asset: str = "equity_domestic",
         q: str = "", sort: str = "sortino", direction: str = "desc", page: int = 1):
    limit, offset = 50, (max(1, page) - 1) * 50
    rows = _rows(window, asset, q, sort, direction, limit, offset)
    return templates.TemplateResponse(request, "_rows.html", {
        "rows": rows, "metrics": METRICS, "window": window,
        "asset": asset, "q": q, "sort": sort, "direction": direction,
        "page": page,
    })


@app.get("/fund/{fund_id}", response_class=HTMLResponse)
def fund_detail(request: Request, fund_id: int):
    with con() as c:
        f = c.execute("SELECT * FROM fund WHERE fund_id = ?", [fund_id]).fetchone()
        fcols = [d[0] for d in c.description]
        ms = c.execute(
            "SELECT * FROM metric WHERE fund_id = ? ORDER BY n_months", [fund_id]).fetchall()
        mcols = [d[0] for d in c.description]
        events = c.execute(
            "SELECT date, label, category, severity FROM market_event ORDER BY date").fetchall()
    fund = dict(zip(fcols, f))
    metrics_by_win = {m[1]: dict(zip(mcols, m)) for m in ms}
    return templates.TemplateResponse(request, "fund.html", {
        "fund": fund, "windows": WINDOWS,
        "metrics_by_win": metrics_by_win, "metric_cols": METRICS,
        "events": [{"date": str(e[0]), "label": e[1], "category": e[2], "severity": e[3]}
                   for e in events],
    })


@app.get("/fund/{fund_id}/series")
def fund_series(fund_id: int, plan: str = "auto"):
    with con() as c:
        f = c.execute(
            "SELECT direct_growth_code, regular_growth_code FROM fund WHERE fund_id = ?",
            [fund_id]).fetchone()
    code = f[0] if (plan != "regular" and f[0]) else f[1]
    path = CACHE_DIR / f"{code}.json.gz"
    if not path.exists():
        return JSONResponse({"t": [], "v": []})
    payload = json.loads(gzip.decompress(path.read_bytes()))
    data = list(reversed(payload.get("data", [])))
    t, v = [], []
    for r in data:
        d, m, y = r["date"].split("-")
        t.append(f"{y}-{m}-{d}")
        v.append(float(r["nav"]))
    return JSONResponse({"t": t, "v": v})
