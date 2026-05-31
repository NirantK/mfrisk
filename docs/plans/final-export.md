# mfrisk — One-Shot Build Export

_Everything needed to reproduce this project from scratch in a single pass:
the distilled spec, the verbatim decisions that shaped it, the Claude Code
hooks/skills/commands used along the way, the technical blueprint, the exact
build sequence, and the non-obvious gotchas that cost time._

Built 2026-05-31. Repo: `github.com/NirantK/mfrisk` (Apache-2.0, public).

---

## 1. The one-shot prompt

> Create a public Apache-2.0 Python repo `mfrisk` under GitHub user NirantK: a
> fast, **local-first** tool that ranks **Indian retail mutual funds** by
> **risk-adjusted** metrics — Sortino, Ulcer (Pain) Index, Martin ratio (UPI),
> plus CAGR / Max Drawdown / Sharpe — across rolling windows **3m, 1Y, 3Y, 5Y,
> 7Y, 10Y, 20Y**. Precompute metrics into local **DuckDB**; serve a fast
> **FastAPI + HTMX + uPlot** microsite for ranking, sorting, and a per-fund NAV
> chart with **major India market-event** overlays.
>
> Data: NAV history from **mfapi.in** (`api.mfapi.in/mf`, `/mf/{code}`); category
> master from **AMFI** (`portal.amfiindia.com/spages/NAVAll.txt`). Cover **all**
> SEBI fund types, ingested in a written priority order (equity first), with a
> stratified **1K sample across all types** as the first demoable slice. Include
> global FoFs (Motilal Oswal Nasdaq 100, Edelweiss Greater China, ICICI US
> Bluechip, etc.). Account for **discontinued / renamed / merged** funds.
>
> Fetch in **parallel, performant, and politely**: bounded concurrency, jittered
> spacing between requests, **exponential backoff with jitter** on 429/5xx,
> resumable cache — never trip a rate limit. Use **uv + pyproject.toml**,
> **polars** (not numpy/pandas) for numerics. Happy-path code, no broad
> try/except (network retries via tenacity).
>
> Seed a **static, version-controlled dictionary** of India market-event dates
> (use web search for exact dates). Restyle the UI to an **Edward Tufte**
> aesthetic with per-row **sparklines** and metric **tooltips**. Verify the
> running site with a headless browser and screenshots.

---

## 2. Verbatim user decisions & preferences (chronological)

These are the user's own words at each turn — the ground truth that overrode any
default. Reproduce these choices exactly.

**Original ask (later superseded):**
> "create a new repo, with Python code, Apache license to help us setup a CLI for
> fast, stock research focussed on India macro and micro data both. For macro …
> data.gov.in and Ministry of Stats."

**The reframe (the real project):**
> "I want to sort mutual funds based on Sortino Adjusted Returns or Ulcer Pain
> Index. Set this up as a microsite to compare based on 3m, 1Y, 3y, 5, 7, 10, 20y
> … Use https://www.mfapi.in/. Explore the website iteratively first to find API
> docs … get atleast >80% of all equity funds. Write data parallel, performant
> code … respectful of rate limits. … exponentially backoff. Add jitter. Also add
> jiterred delay in parallel requests. Prefer uv with pyproject.toml. Account for
> funds which have been discontinued, renamed, or merged … exclusively for India
> Retail mutual funds but FoF investing globally e.g. Motilal Oswal Nasdaq 100,
> Edelweiss China, should definitely be included. Mark major dates … which have
> impacted Indian markets … Create a saved, static dictionary first. Write all of
> this into a set of architecture or planning markdown files. Keep the microsite
> fast with HTMX and local … Ultrathink."

**Four scoping decisions (answers to multiple-choice questions):**
1. Plan/window resolution → **"Direct ≤10Y, Regular >10Y"** (Direct plans only
   exist since Jan 2013, so 20Y must come from Regular-Growth).
2. Stack → **"DuckDB + FastAPI + HTMX"**.
3. Metric convention → **"Monthly NAV, MAR=RFR"**.
4. Universe → **"Everything, but show me a working updated demo every 5K funds,
   starting with equity + global, include hybrid, debt and every other type of
   fund e.g. multi asset"**.

**Then, turn by turn:**
- "Make sure the docs are not repeating the same thing? Make a pass using a
  subagent." → each doc owns its topic; shared facts have one canonical home.
- Repo name **"mfrisk"**, visibility **Public**.
- "Update the priority sequence and make sure we create an initial sample of 1K
  funds across all types (recheck for types if you don't have it hot) and then
  setup a background subagent with the written priority sequence."
- `/goal` → "run until microsite is up and verified via screenshot to be
  effective" … "to be correct and sort via multiple criteria".
- "Use polars over numpy".
- `/goal` → "improve readability by using /browse in a loop till it's excellent"
  … "Restyle using /tufte-viz aesthetics".
- "Use a higher readability font. Ask /advisor for font suggestions which are
  different from Claude." → shipped **Source Serif 4** (data) + **Spectral**
  (headings); advisor argued *against* Atkinson Hyperlegible for a Tufte page.
- "Add a tooltip where we concisely explain the metric".
- "Make sure you also check that secondary sort works. And for all metrics,
  higher is better." → uniform higher-is-better sort.
- "Bug report: On hover for tooltip, the source text is flickering".
- "Update README to have the startup instructions and our preferences".
- "Remove the secondary sort, does not seem to be adding value" → removed it.

**Standing global preferences (from the user's CLAUDE.md — always in force):**
- Never mention Claude/Anthropic in commit messages.
- Use `uv run`, not `python`.
- `gh` CLI for PRs; keep PR body < 5 lines; no test-plan section.
- **Happy-path conventions; no broad try/except blocks.**
- Never `git push --force` / `-f`; make new commits instead.
- Prefer ripgrep / ugrep / ast-grep over grep.
- DATETIME rule: run `date` (IST, `TZ=Asia/Kolkata`) before stating any day/date.
- All web browsing via **`/browse`** (gstack); never the Chrome MCP tools.
- PERFORMANCE rule: design IO/network/compute for parallelism, batching,
  backoff+retry, resumability by default.

---

## 3. Claude Code environment used (hooks · skills · commands)

This project leaned on Claude Code-specific machinery. To reproduce the *workflow*
(not just the artifact):

**Hooks**
- `SessionStart` hooks injected: a **caveman-mode** narration style and the
  **superpowers** `using-superpowers` skill (forces skill use before acting).
- **`/goal` Stop hooks** — session-scoped conditions that *block the agent from
  stopping* until satisfied (e.g., "microsite up and verified via screenshot",
  "sort via multiple criteria"). These drove the autonomous build-and-verify
  loops. They auto-clear when the condition holds.

**Skills (invoked via the `Skill` tool / slash commands)**
- **`superpowers:brainstorming`** — used *first*, before any code, to explore
  intent and lock the four scoping decisions (process-before-implementation).
- **`tufte-viz`** — Tufte principles for the readability restyle (data-ink ratio,
  hairline rules, sparklines, eraser/collision tests).
- **`/browse`** (gstack headless Chromium) — `goto`, `screenshot --clip`, `js`,
  `hover`, `console --errors`, `viewport --scale` for screenshot verification.

**Agents / tools**
- **`Agent` tool (subagents)**: a doc-dedup audit pass; a **background subagent**
  to run the full priority-ordered ingest; a "typography advisor" subagent
  (stood in for the requested `/advisor`). Background agents notify on completion.
- **`AskUserQuestion`** for the four scoping decisions (multiple choice).
- `WebSearch` / `WebFetch` for event dates and API grounding; `ToolSearch` to load
  deferred tools (WebFetch/WebSearch/Chrome).
- Note: `/advisor` is not a built-in skill here — it was fulfilled with a
  general-purpose advisor subagent. Swap in your own advisor if you have one.

**Commit/PR conventions**: terse messages, `Co-Authored-By` trailer, no
Claude/Anthropic mentions, never force-push.

---

## 4. Technical blueprint (condensed)

**Data sources (verified live)**
- `GET api.mfapi.in/mf` → ~**37,613** schemes `{schemeCode, schemeName, isin…}`
  (includes dead/merged). `GET /mf/{code}` → `{meta{fund_house, scheme_type,
  scheme_category…}, data:[{date:"DD-MM-YYYY", nav}], status}`, newest-first to
  inception. `/mf/search?q=` for ad-hoc lookups.
- AMFI `portal.amfiindia.com/spages/NAVAll.txt` (the `www.` URL 302-redirects) —
  one semicolon file, **active** schemes grouped under exact SEBI category
  headers. Same scheme codes as mfapi → cheap pre-classification; dead = in mfapi
  but absent here.

**Classification** (`catalog.py`): category-first, then a name-keyword pass for the
ambiguous `Index Funds` / `FoF` buckets (Nasdaq/S&P/China/Nifty = equity-global;
SDL/Gilt/Treasury/Bond = debt). 10 asset classes; ~**2,665 canonical Growth funds**.

**Canonical fund identity**: group `{Direct,Regular} × Growth` codes by
`(fund_house, base_name, asset_class)` where `base_name` strips plan/option tokens.
**Growth option only** (IDCW/dividend/bonus dropped — payouts corrupt return series).

**Plan resolution per window**: Direct-Growth for ≤10Y (fall back Regular),
**Regular-Growth for 20Y** (Direct plans began 1 Jan 2013). Store `plan_used`.

**Fetcher** (`fetch.py`, httpx async): `asyncio.Semaphore` (default 8) + jittered
spacing (~0.15s + rand·0.25s) + **tenacity** `wait_random_exponential` backoff with
full jitter on 429/5xx/transport errors. Cache = `data/cache/<code>.json.gz`;
**file-existence = resumability**. Full universe ≈ 3–4 min, zero rate-limit hits.

**Priority order** (`priority.py`, single source of truth):
`equity_domestic → equity_global → equity_passive → hybrid → hybrid_multiasset →
hybrid_arbitrage → solution → commodity → debt → other`. The 1K sample is
stratified across all 10 (proportional, floor 20/class, evenly spaced by name).

**Metrics** (`metrics.py`, **polars** only): month-end NAV → monthly returns;
RFR 6%, MAR = monthly RFR. Sortino = (annualised return − RFR) / annualised
downside deviation; Sharpe vs total vol; **Ulcer Index** = `sqrt(mean(drawdown²))`
on the daily series; Max DD = min drawdown; **Martin** = excess / Ulcer; CAGR from
month-end endpoints. **Higher is better for every metric** (uniform sort
direction). Output: `fund`, `metric`, `market_event` tables + a precomputed
`fund.spark` monthly-NAV path for row sparklines.

**Microsite** (`web/app.py` + Jinja/HTMX): `/` rank view (window · asset class ·
rank-by metric · order · search, all HTMX-swapped), `/rank` partial, `/fund/{id}`
detail with per-window metric grid + uPlot NAV chart + event overlays,
`/fund/{id}/series` JSON. **Tufte** styling: ivory ground, hairline horizontal
rules, restrained color, per-row sparklines, Source Serif 4 + Spectral fonts,
tabular numerals, metric-header tooltips.

**Market events** (`data/market_events.py`): static typed list, 19 entries
(Harshad Mehta → dot-com → GFC → taper → demonetisation → IL&FS → COVID →
Russia-Ukraine → Adani-Hindenburg → 2024 election → yen carry-trade), each with
`date/label/category/severity/note`, overlaid on charts.

---

## 5. Build sequence (exact)

```bash
# scaffold
uv init / create pyproject (deps: httpx[http2], duckdb, polars, typer, tenacity;
                            extra web: fastapi, uvicorn[standard], jinja2)
curl -sL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE

# build + run
uv sync --extra web
uv run mfrisk catalog                 # AMFI parse + classify + plan-group
uv run mfrisk ingest --sample         # 1K stratified sample (all types) first
uv run mfrisk ingest --all            # full universe in priority order, resumable
uv run mfrisk compute                 # metrics -> data/mfrisk.db
uv run mfrisk serve                   # http://127.0.0.1:8000
uv run mfrisk status                  # cache progress by asset class
uv run mfrisk events                  # static event dictionary

# verify (gstack /browse)
$B goto http://127.0.0.1:8000/ ; $B console --errors ; $B screenshot out.png --clip ...
```

Outcome: **5,092 schemes / 7.7M NAVs** cached; **2,636 funds / 10,167 metric
rows**. `data/` is gitignored; everything regenerates from the commands above.

---

## 6. Gotchas (these cost real time — bake the fixes in)

1. **AMFI `www.` URL 302-redirects** to `portal.amfiindia.com`; follow it
   (`curl -L`) or you get an "Object Moved" stub.
2. **`window` is a reserved word in DuckDB** — name the column `win`, not
   `window`, or every query throws a ParserException.
3. **Starlette `TemplateResponse` signature is `(request, name, context)`** in
   current versions; the old `(name, {"request":…})` form raises
   `TypeError: unhashable type: 'dict'`.
4. **NAV data artifacts**: ~5.7% of series have a >50% single-day jump from
   face-value resets / scheme-code reuse / merges (e.g. ₹10→₹1,006). Left
   uncleaned they inflate 20Y money-market CAGR to ~41%. Fix: truncate each
   series to the clean segment **after the last >50% single-day jump**.
5. **Direct plans start 1 Jan 2013** — 20Y windows are empty for Direct; must use
   Regular-Growth. Drives the whole plan-resolution rule.
6. **Sticky-header CSS tooltip flicker**: setting `position:relative` on `:hover`
   *overrides* the header's `position:sticky`, so the header drops out of sticky,
   shifts, loses hover, and loops. Fix: never change `position` on hover (sticky
   already anchors the `::after`), and give the bubble `pointer-events:none`.
7. **Sticky `thead` overlap**: its `top` offset must equal the masthead height,
   with a solid (opaque) background and a `z-index` below the masthead but above
   rows — else the first data row bleeds through the header on scroll.
8. **Kill the server by port** (`lsof -ti:8000 | xargs kill`) between runs;
   uvicorn without `--reload` keeps serving stale code and a `pkill` by module
   name can miss it (you debug a fix that's "not working" because the old process
   answered).
9. **Restart after template/CSS edits** — Jinja caches templates; restart so
   changes show, and hard-reload to bust the browser's CSS cache.
10. **Removed**: secondary ("then by") sort — built and verified, then cut per
    user ("does not seem to be adding value"). Don't re-add.

---

## 7. File map

```
src/mfrisk/
  cli.py            # typer: catalog · ingest · compute · serve · status · events
  priority.py       # the written 10-tier ingest priority sequence
  catalog.py        # AMFI parse + classification + Direct/Regular plan grouping
  fetch.py          # async httpx fetcher (concurrency, jitter, tenacity backoff)
  metrics.py        # polars metrics engine + sparkline + DuckDB writer
  data/market_events.py   # static India market-event dictionary
  web/app.py        # FastAPI + HTMX routes
  web/templates/    # base · index · _rows (partial) · fund
  web/static/style.css    # Tufte aesthetic
docs/plans/         # architecture · data-ingestion · metrics · microsite · roadmap · this file
LICENSE  pyproject.toml  README.md
```
