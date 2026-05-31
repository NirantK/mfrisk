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

## Quickstart (planned)

```bash
uv sync
uv run mfrisk ingest          # fetch NAV history, resumable, rate-limited
uv run mfrisk compute         # precompute metrics into DuckDB
uv run mfrisk serve           # FastAPI + HTMX microsite at :8000
```

## Design docs

- [Architecture](docs/plans/2026-05-31-architecture.md)
- [Data ingestion](docs/plans/2026-05-31-data-ingestion.md)
- [Metrics](docs/plans/2026-05-31-metrics.md)
- [Microsite](docs/plans/2026-05-31-microsite.md)
- [Roadmap & milestones](docs/plans/2026-05-31-roadmap.md)

## Status

Planning. See design docs above. Data layer grounded against the live
mfapi.in + AMFI endpoints (37,613 schemes; ~700–900 canonical equity funds,
all fund types ingested in priority order).
