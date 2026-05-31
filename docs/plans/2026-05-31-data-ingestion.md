# Data Ingestion — mfrisk

_Date: 2026-05-31_

## Sources (verified live 2026-05-31)

### mfapi.in — NAV history
- `GET https://api.mfapi.in/mf` → **37,613** schemes, each
  `{schemeCode, schemeName, isinGrowth, isinDivReinvestment}`. Includes dead /
  merged / renamed schemes (full historical universe).
- `GET https://api.mfapi.in/mf/{schemeCode}` → `{meta, data, status}`:
  - `meta`: `fund_house`, `scheme_type` (e.g. "Open Ended Schemes"),
    `scheme_category` (e.g. "Equity Scheme - Large Cap Fund"), `scheme_code`,
    `scheme_name`, `isin_growth`, `isin_div_reinvestment`.
  - `data`: list of `{date: "DD-MM-YYYY", nav: "string"}`, **newest first**,
    back to inception (observed to 2006/2013 on samples; older for legacy funds).
  - `status`: "SUCCESS" / failure.
- `GET .../{schemeCode}/latest` → same shape, single latest NAV.
- `GET https://api.mfapi.in/mf/search?q=<term>` → name search (used for
  ad-hoc lookups, not bulk).

### AMFI — category master + ISIN
- `GET https://portal.amfiindia.com/spages/NAVAll.txt` (the
  `www.amfiindia.com/...` URL 302-redirects here — follow it).
- Semicolon-delimited: `Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div
  Reinvestment;Scheme Name;Net Asset Value;Date`.
- Grouped under **category header lines** (no `;`), exactly the SEBI taxonomy,
  e.g. `Open Ended Schemes(Equity Scheme - Large Cap Fund)`, preceded by an AMC
  name line. **~17.6K active rows**. Scheme codes match mfapi's.
- This is the **pre-classification key**: one cheap file gives category + ISIN +
  "is active today" for the whole live universe, so we do **not** probe 37K
  scheme metas blindly.

## Classification

`asset_class` derived in two passes:

1. **Category-first** from AMFI/mfapi `scheme_category`:
   - `Equity Scheme - *` → equity (sub = Large/Mid/Small/Flexi/ELSS/…).
   - `Hybrid Scheme - *` → hybrid (Aggressive Hybrid flagged equity-oriented).
   - `Debt Scheme - *` → debt. `Solution Oriented - *` → solution.
   - `Other Scheme - Gold ETF / Other ETFs` → commodity/etf.
2. **Name-keyword refinement** for the ambiguous buckets
   (`Other Scheme - Index Funds`, `FoF Overseas`, `FoF Domestic`):
   - equity-global if name matches `nasdaq|s&p ?500|china|us |global|world|
     hang seng|emerging|nifty|sensex|midcap|smallcap|developed|innovation|
     fang|qqq|eqqq|nasdaq-?100`;
   - debt if `sdl|gilt|g-?sec|treasury|bond|psu|liquid|duration|aaa|crisil ?ibx`.

`is_global = True` for overseas exposure (FoF Overseas, US/China/Japan/Nasdaq/
S&P names) — these are **in scope** per requirements (Motilal Oswal Nasdaq 100,
Edelweiss Greater China, ICICI US Bluechip, etc., all confirmed present).

Observed equity-scope active counts (AMFI, all plan/option variants): **4,137**;
canonical **Direct-Growth ≈ 1,036** before debt-index/FoF trimming →
**~700–900 true equity funds**. Full universe (all asset classes, canonical
Growth plans) ≈ **8–12K funds**.

## Plan / option grouping → "fund"

Each fund carries many scheme codes: `{Regular, Direct} × {Growth, IDCW,
IDCW-Reinvest, Bonus}`. For risk metrics:

- **Canonical = Growth option only** (IDCW NAVs drop on payout → corrupt return
  series). Drop IDCW/Dividend/Bonus codes from metric computation.
- **Plan resolution per window** (locked decision):
  - 3m, 1Y, 3Y, 5Y, 7Y, 10Y → **Direct-Growth** if it spans the window, else
    fall back to Regular-Growth.
  - 20Y (and any window starting before 2013-01-01) → **Regular-Growth**.
  - Record `plan_used` per metric row so the UI can label it.
- **Identity key**: `(fund_house, normalized_base_name, asset_class)` where
  `normalized_base_name` strips plan/option/qualifier tokens (`direct|regular|
  growth|idcw|dividend|bonus|plan|option|payout|reinvest`), punctuation, and
  collapses whitespace. ISIN growth is a secondary join hint.

## Dead / renamed / merged funds

- **Dead/merged detection**: a scheme code present in mfapi but **absent from
  today's AMFI NAVAll** → `active = False`. Also flag `active = False` if the
  latest mfapi NAV date is older than **45 days** (configurable) — captures
  funds frozen mid-month before formal removal.
- **Renamed**: same scheme code, changed `scheme_name` over time. AMFI/mfapi
  keep the code stable, so history is continuous — we keep the **latest** name
  as `display_name`, store nothing special beyond that.
- **Merged**: predecessor fund's code goes inactive; successor is a different
  code with its own history. v1 keeps them as **separate funds** (no synthetic
  splicing — that would fabricate returns). The predecessor still contributes
  real 10Y/20Y history while it was live. A future enhancement may add a manual
  `merge_map` for known mergers; out of scope for v1.

## Async fetch — performance & politeness

Requirement: fetch as much as possible, fast, **without ever hitting a rate
limit**; exponential backoff **with jitter**; jittered delay between parallel
requests. mfapi publishes no formal limit, so we self-throttle conservatively.

Design (`fetch/client.py`):

- **`httpx.AsyncClient`** with HTTP/2, keep-alive, shared connection pool.
- **Bounded concurrency** via `asyncio.Semaphore`, default **8** in-flight
  (configurable `--concurrency`). Conservative on purpose.
- **Per-request jittered spacing**: before each request, `await asyncio.sleep(
  base_delay + random.uniform(0, jitter))` with `base_delay≈0.15s`,
  `jitter≈0.25s` per worker → smooths bursts even at full concurrency.
- **Retry with exponential backoff + full jitter** on `429`, `5xx`, timeouts,
  connection errors:
  `sleep = random.uniform(0, min(cap, base * 2**attempt))`, `base=0.5s`,
  `cap=30s`, **max 6 attempts**. Honour `Retry-After` if present.
- **Adaptive cooldown**: on any `429`, halve effective concurrency for the next
  N requests and widen `base_delay`; recover slowly. One 429 should never
  cascade.
- **Timeouts**: connect 10s, read 30s (histories can be large).
- **Idempotent + resumable**: each scheme's result written immediately; rerun
  skips `status='ok'` codes. Safe to Ctrl-C and resume.

Throughput sanity: ~8 concurrent × ~0.2s effective spacing ≈ 30–40 req/s
sustained → full 37K universe in ~15–20 min, canonical equity slice in ~1–2 min.
We deliberately stay well under any plausible limit; correctness/politeness over
raw speed.

## Priority sequence (updated)

Asset classes are derived in `catalog.py` (category-first + name-keyword). The
**ingest priority sequence** — the single source of truth, encoded in
`fetch/priority.py` — orders funds equity-first, liquid-debt-last:

| # | Asset class | Active canonical funds | What it covers |
|---|---|---|---|
| 1 | `equity_domestic` | 603 | Large/Mid/Small/Flexi/Multi/Focused/Value/Contra/Div-Yield/ELSS/Sectoral-Thematic |
| 2 | `equity_global` | 69 | FoF Overseas + global equity (Nasdaq, S&P 500, China, US, Japan, EM) |
| 3 | `equity_passive` | 372 | Domestic equity index funds + equity ETFs |
| 4 | `hybrid` | 120 | Aggressive Hybrid, BAF/Dynamic AA, Equity Savings, Conservative, Balanced |
| 5 | `hybrid_multiasset` | 35 | Multi Asset Allocation |
| 6 | `hybrid_arbitrage` | 41 | Arbitrage |
| 7 | `solution` | 39 | Retirement, Children's |
| 8 | `commodity` | 46 | Gold / Silver ETF & FoF |
| 9 | `debt` | 682 | Liquid/Overnight/MM → Ultra/Low/Short → Corp/Banking-PSU/Credit → Gilt/Long/Dynamic → target-maturity SDL/Gilt index |
| 10 | `other` | 658 | IDF, close-ended income/growth, interval, unclassified |

≈ **2,665 active canonical Growth funds** total (counts from AMFI master,
2026-05-31). Within a tier, order by fund so a fund's Direct + Regular codes land
together (rankable as soon as fetched). Inactive/dead predecessors are appended
per tier for long-window history (follow-up after the active run).

`fetch/runner.py`:

- Build the work-list of **canonical Growth scheme codes** (Direct + Regular)
  in the priority sequence above.
- Persist progress in `ingest_state` (cache-file existence + status row);
  `--resume` (default) skips already-fetched codes.
- **Checkpoint every 5,000 schemes**: trigger `metrics.compute` for funds whose
  required series are now complete, so the microsite shows a **growing, working
  demo** at each milestone. Emit `checkpoint N: M funds rankable (equity X…)`.
- `mfrisk status` prints counts by status/asset class and the last checkpoint.

## Initial 1K stratified sample (across all types)

Before the full run, `mfrisk ingest --sample 1000` fetches a **stratified**
1,000-fund slice so **every** asset class is represented from the start (not just
the top priority tier). Allocation: proportional to each class's canonical count,
**floored at 20 per class** (capped at availability), renormalized to 1,000.
Within a class, funds are picked **evenly spaced by name** to span AMCs rather
than clustering on one house. This sample is the first demoable dataset; the
background full run then continues in priority order, reusing the same cache.

## Failure handling (happy-path friendly)

- A scheme returning `status != SUCCESS`, empty `data`, or unparseable NAV →
  marked `status='empty'` in `ingest_state`, excluded from metrics, **not**
  retried endlessly. No exceptions thrown into the run loop; bad schemes are
  data, not crashes.
- Network/5xx/429 handled by the retry layer above; only after max attempts is a
  code marked `status='error'` for a later targeted re-run.
