# mfrisk

Fast, local-first research for **Indian retail mutual funds**, ranked by
**risk-adjusted** metrics — Sortino ratio and the Ulcer Pain Index / Martin
ratio — across rolling windows (3m, 1Y, 3Y, 5Y, 7Y, 10Y, 20Y).

Data comes from public NAV history ([mfapi.in](https://www.mfapi.in/)) and the
AMFI category master. Metrics are precomputed into a local DuckDB file and served
by a fast FastAPI + HTMX microsite for sorting and side-by-side comparison, with
major India market-event dates overlaid on every chart.

> Repo name `mfrisk` is a placeholder — rename in `pyproject.toml` + dir if you
> prefer something else. Apache-2.0 licensed.

## Why

Most fund comparison tools rank on trailing returns alone. Returns ignore *how
much pain* you endured to get them. `mfrisk` ranks on:

- **Sortino ratio** — return per unit of *downside* volatility (ignores upside
  noise that Sharpe penalises).
- **Ulcer Index** — depth × duration of drawdowns; the felt "pain" of holding.
- **Martin ratio (UPI)** — excess return per unit of Ulcer Index.

## Startup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
# 1. install deps (web extra pulls FastAPI/uvicorn/jinja for `serve`)
uv sync --extra web

# 2. build the catalog: parse AMFI master + classify + group Direct/Regular
#    -> data/catalog/{funds,worklist,sample_1k}.json
uv run mfrisk catalog

# 3. fetch NAV history into the resumable cache (data/cache/*.json.gz)
uv run mfrisk ingest --sample            # quick: 1K stratified sample, all types
uv run mfrisk ingest --all               # full universe, priority order (~3 min)
#   optional: --tier equity_domestic     restrict to one asset class
#             --concurrency 8            in-flight requests (default 8)

# 4. precompute risk-adjusted metrics -> data/mfrisk.db (DuckDB)
uv run mfrisk compute

# 5. serve the microsite at http://127.0.0.1:8000
uv run mfrisk serve                       # --host / --port to override

# utilities
uv run mfrisk status                      # cache progress by asset class
uv run mfrisk events                      # the static market-event dictionary
```

`ingest` is **resumable and rate-limited** — safe to Ctrl-C and re-run; it skips
already-cached schemes and never hammers mfapi (bounded concurrency, jittered
spacing, exponential backoff with jitter on 429/5xx). `data/` is gitignored;
regenerate anytime with the steps above.

## Preferences (conventions baked in)

**Stack** — uv + `pyproject.toml`; **polars** for all numerics (no numpy/pandas);
**DuckDB** store; **FastAPI + HTMX + uPlot** frontend (no build step, no SPA).

**Metric conventions** — month-end NAV returns; MAR (minimum acceptable return) =
risk-free rate, default **6%** annual (`RFR` in `metrics.py`). Ulcer Index and max
drawdown use the daily series within the window. **Higher is better for every
metric** — sort direction is uniform, no per-metric flipping.

**Plan resolution** — Direct plans only exist since Jan 2013, so windows ≤ 10Y use
**Direct-Growth** (fall back to Regular), and 20Y uses **Regular-Growth**. Each
metric row records the `plan_used`.

**Data hygiene** — only the **Growth** option is canonical (IDCW/dividend/bonus
dropped). NAV series are cleaned of face-value-reset / merge artifacts (any >50%
single-day jump truncates to the clean recent segment). Dead/merged funds are kept
for long-window history and flagged inactive (latest NAV > 45 days old).

**Ingest priority** — `priority.py` is the single source of truth: equity_domestic
→ equity_global → equity_passive → hybrid → multiasset → arbitrage → solution →
commodity → debt → other. The 1K sample is stratified across all 10 classes.

**Design** — Tufte aesthetic: ivory ground, hairline rules, high data-ink,
restrained color, per-row NAV sparklines. Fonts: **Source Serif 4** (data) +
**Spectral** (headings), tabular figures.

**Code style** — happy-path, no broad `try/except` (network retries via tenacity).
Commits and PRs stay terse.

## Design docs

- [Architecture](docs/plans/2026-05-31-architecture.md)
- [Data ingestion](docs/plans/2026-05-31-data-ingestion.md)
- [Metrics](docs/plans/2026-05-31-metrics.md)
- [Microsite](docs/plans/2026-05-31-microsite.md)
- [Roadmap & milestones](docs/plans/2026-05-31-roadmap.md)

## Status

Working end to end. **5,092 schemes / 7.7M NAVs** cached; **2,636 funds /
10,167 metric rows** computed across all SEBI fund types. Rank, sort, search,
fund detail with event-overlaid NAV chart, and the metrics engine are live.
