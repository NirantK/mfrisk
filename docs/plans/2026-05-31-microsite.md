# Microsite — mfrisk

_Date: 2026-05-31 · FastAPI + HTMX + DuckDB + uPlot_

## Goals

Local, instant, no-build frontend over the precomputed `metric` table. Sort the
whole universe by any risk-adjusted metric for any window; compare funds side by
side; per-fund detail with a NAV chart and **market-event overlays**. Server
holds all logic; HTMX swaps HTML partials — no SPA, no bundler.

## Routes

| Method · Path | Purpose | Returns |
|---|---|---|
| `GET /` | Rank view (default: Sortino, 3Y, equity). | Full page |
| `GET /rank` | HTMX partial: ranked rows for `?metric=&window=&asset=&q=&sort=&page=`. | `<tbody>` partial |
| `GET /fund/{fund_id}` | Fund detail: all-window metric grid + NAV chart + events. | Full page |
| `GET /fund/{fund_id}/series?window=` | uPlot JSON (dates, nav) + event markers. | JSON |
| `GET /compare?ids=a,b,c` | Side-by-side metric grid for 2–4 funds. | Full page / partial |
| `GET /events` | The static market-event table (also drives overlays). | Full page |
| `GET /status` | Ingest/compute progress (counts, last checkpoint). | Full page |

## Rank view (the core screen)

- Controls (HTMX-driven, no reload): **metric** selector (Sortino / Ulcer Index
  / Martin / CAGR / Max DD / Sharpe), **window** chips (3m·1Y·3Y·5Y·7Y·10Y·20Y),
  **asset-class** filter (Equity / Global / Hybrid / Debt / All), free-text
  **search**, column-header sort, pagination.
- Each control change fires `hx-get="/rank"` with `hx-include` on the form,
  swapping just the table body. Sub-100ms because rows come straight from a
  DuckDB-indexed `metric` query.
- Row: fund name · house · category · plan_used badge · the chosen metric (bold)
  · CAGR · Ulcer · Max DD · checkbox to add to Compare.
- Lower Ulcer/Max-DD render green→red; Sortino/Martin/CAGR high render green.

## Fund detail

- Metric grid: rows = windows, cols = {CAGR, Sortino, Ulcer, Martin, MaxDD,
  Sharpe}, with `plan_used` noted per row (Direct vs Regular).
- **NAV chart (uPlot)**: log-scale NAV over the selected window with **vertical
  event lines** + hover labels from `market_event`. Toggle daily/normalized.
- "Active/Inactive" badge; if inactive, show last NAV date and likely status
  (merged/discontinued) from `ingest_state`.

## Compare

- 2–4 funds chosen via rank-view checkboxes → `/compare?ids=…`. Aligned metric
  grid per window; optional overlaid normalized-NAV uPlot (rebased to 100 at
  window start) with shared event overlays.

## Event overlays

- Source: `market_event` table, seeded from `data/market_events.py` (static,
  version-controlled). Rendered as uPlot plugin drawing vertical rules + tags;
  `severity` controls opacity, `category` controls colour
  (crash / policy / global / geopolitical / sector).

## Tech notes

- **FastAPI** async app; **Jinja2** templates; **HTMX** via one `<script>` CDN/
  vendored file; **uPlot** vendored in `web/static/`. No Node, no build step.
- DuckDB opened read-only in the web process (ingest/compute write separately);
  queries are simple indexed selects + `ORDER BY` + `LIMIT/OFFSET`.
- `uv run mfrisk serve` runs uvicorn on `:8000`. Single command, fully local.
- Graceful empty state: if `metric` is sparse (early checkpoint), UI still works
  and shows "computed so far" counts — supports the 5K-fund demo cadence.
