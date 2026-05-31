# Architecture — mfrisk

_Date: 2026-05-31 · Status: design approved (brainstorm), pre-implementation_

## Context

Indian retail investors compare mutual funds almost entirely on trailing
returns. Returns say nothing about the **drawdown pain** taken to earn them.
`mfrisk` is a local-first tool that ranks every Indian MF by **risk-adjusted**
metrics (Sortino, Ulcer Index, Martin ratio) across standard windows, computed
from full NAV history, served through a fast HTMX microsite. It must:

- cover the **whole** Indian MF universe (all SEBI fund types), ingested in
  priority order (equity + global equity first, then hybrid, debt, multi-asset,
  the rest), **resumable**, with a working demo refreshed **every ~5K funds**;
- be **respectful of mfapi.in** — bounded concurrency, jittered delays,
  exponential backoff with jitter, zero rate-limit hits;
- correctly handle **plan/option variants** (Direct vs Regular, Growth vs IDCW)
  and **dead / renamed / merged** funds so long windows are real, not
  survivorship-biased;
- overlay **major India market-event dates** (a static, version-controlled
  dictionary) on charts.

## Decisions (locked)

| Area | Decision |
|---|---|
| Series per window | **Direct-Growth for ≤10Y**, **Regular-Growth for >10Y** (Direct plans only exist since 1 Jan 2013). Group plans under one logical fund. |
| Stack | **DuckDB** (analytics store) + **FastAPI** (async) + **HTMX** (frontend), **uPlot** for charts. |
| Metric convention | **Month-end NAV** returns; downside relative to **MAR = risk-free rate** (default RFR 6% annual, configurable). |
| Universe | **All fund types**, priority-ordered ingest, 5K-fund demo cadence. |
| Packaging | **uv** + `pyproject.toml`, Python 3.12+. |
| License | Apache-2.0. |

## Component map

```
                    ┌──────────────────────────────────────────────┐
                    │                CLI (Typer)                    │
                    │   ingest · compute · serve · status · events  │
                    └───────┬───────────────┬──────────────┬───────┘
                            │               │              │
                ┌───────────▼──┐   ┌────────▼───────┐   ┌──▼─────────┐
                │  Catalog     │   │  Fetcher       │   │  Metrics    │
                │  (AMFI+mfapi)│   │  (async, RL,   │   │  engine     │
                │  classify +  │   │   backoff,     │   │  (monthly,  │
                │  plan-group  │   │   resumable)   │   │   Sortino,  │
                └───────┬──────┘   └───────┬────────┘   │   Ulcer…)   │
                        │                  │            └──────┬──────┘
                        ▼                  ▼                   ▼
                 ┌─────────────────────────────────────────────────┐
                 │                   DuckDB (mfrisk.db)             │
                 │  scheme · nav · fund · metric · ingest_state     │
                 │  market_event (seeded from static dict)          │
                 └─────────────────────────┬───────────────────────┘
                                           │
                                  ┌────────▼─────────┐
                                  │ FastAPI + HTMX   │
                                  │ rank · compare · │
                                  │ fund detail      │
                                  └──────────────────┘
```

## Module layout

```
src/mfrisk/
  __init__.py
  cli.py                 # Typer entrypoints: ingest/compute/serve/status/events
  config.py              # settings (RFR, concurrency, paths) via pydantic-settings
  catalog/
    amfi.py              # parse AMFI NAVAll.txt -> active schemes + SEBI category
    classify.py          # category + name-keyword -> asset class & equity/global
    plan_group.py        # group Direct/Regular/Growth/IDCW into one fund identity
  fetch/
    client.py            # async httpx client: concurrency, jitter, backoff+jitter
    scheme_history.py    # /mf/{code} -> normalized NAV series; dead-fund detection
    runner.py            # resumable, priority-ordered batch ingest; 5K checkpoints
  metrics/
    series.py            # month-end resample, returns, gap handling
    risk.py              # sortino, ulcer_index, martin, max_drawdown, cagr, sharpe
    windows.py           # 3m/1Y/3Y/5Y/7Y/10Y/20Y window cuts + plan resolution
    compute.py           # per-fund × per-window metric table -> DuckDB
  store/
    db.py                # DuckDB connection, schema DDL, upsert helpers
    schema.sql
  data/
    market_events.py     # STATIC dictionary of India market-event dates (seed)
  web/
    app.py               # FastAPI app + routes
    templates/           # Jinja2 + HTMX partials
    static/              # uPlot, minimal CSS
docs/plans/              # these design docs
tests/
```

## Data flow

1. **Catalog.** Download AMFI `NAVAll.txt` → active scheme codes + exact SEBI
   category + ISIN. Cross-join with the mfapi full list to discover **inactive**
   codes (in mfapi, absent from AMFI = dead/merged/renamed). `classify.py` maps
   category→asset class, with a name-keyword pass for the ambiguous Index/FoF
   buckets. Counts, endpoints, and keyword rules live in the ingestion doc.
2. **Plan grouping.** Collapse the ~37K plan/option codes into logical **funds**.
   Identity key = (fund_house, normalized base name, asset class). Each fund
   tracks its Direct-Growth and Regular-Growth scheme codes (+ inactive
   predecessors) for window resolution.
3. **Fetch.** `runner.py` walks funds in priority order, fetching each needed
   scheme's full NAV history via mfapi, normalizing to `(date, nav)`. Resumable
   via `ingest_state`; respects rate limits (see ingestion doc).
4. **Compute.** For each fund × window, resolve the right plan series, resample
   to month-end, compute the metric set, upsert into `metric`.
5. **Serve.** FastAPI reads precomputed `metric` rows; HTMX renders sortable rank
   tables, comparison, and per-fund detail with event overlays.

## Storage schema (DuckDB)

- `scheme(scheme_code PK, scheme_name, fund_house, sebi_category, asset_class,
  is_equity, is_global, plan, option, isin, fund_id, active, last_nav_date)`
- `nav(scheme_code, date, nav)` — daily, as published.
- `fund(fund_id PK, display_name, fund_house, asset_class, category,
  direct_growth_code, regular_growth_code, inception_date)`
- `metric(fund_id, window, plan_used, as_of, cagr, sortino, ulcer_index, martin,
  max_drawdown, sharpe, vol, downside_dev, n_months)` — the table the UI ranks.
- `ingest_state(scheme_code, status, last_nav_date, fetched_at, http_status)` —
  resumability + dead-fund tracking.
- `market_event(date, label, category, severity, note)` — seeded from
  `data/market_events.py`.

## Non-goals (YAGNI)

- No portfolio/holdings construction, transactions, or P&L.
- No live/intraday NAV; daily published NAV is sufficient.
- No auth, no multi-user, no cloud deploy in v1 — local-first.
- No benchmark/index-relative alpha in v1 (Sharpe/Sortino vs RFR only).

## Verification

- `uv run mfrisk ingest --limit 200 --only equity` fetches a small slice without
  tripping limits; `mfrisk status` shows counts by status.
- `uv run mfrisk compute` produces `metric` rows; spot-check a known fund (e.g.
  SBI Large Cap, code 119598) Sortino/Ulcer against a hand calc in a notebook.
- `uv run mfrisk serve` → rank table sorts by Sortino/Ulcer per window; compare
  two funds; detail chart shows event overlays.
- `pytest` covers metric math against synthetic series with known answers.
