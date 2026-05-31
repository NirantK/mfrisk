"""mfrisk CLI — catalog, ingest, status."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer

from . import catalog as catalog_mod
from . import fetch as fetch_mod
from .priority import PRIORITY_SEQUENCE

app = typer.Typer(add_completion=False, help="Risk-adjusted Indian mutual-fund research.")

DATA = Path("data")
CATALOG_DIR = DATA / "catalog"
CACHE_DIR = DATA / "cache"


@app.command()
def catalog(
    navall: Optional[Path] = typer.Option(None, help="Local AMFI NAVAll.txt (else fetch)."),
    mflist: Optional[Path] = typer.Option(None, help="Local mfapi list json (else fetch)."),
    sample: int = typer.Option(1000, help="Stratified sample size."),
):
    """Build canonical fund universe + worklist + stratified sample."""
    summary = catalog_mod.build(CATALOG_DIR, navall, mflist, sample)
    typer.echo(f"funds={summary['funds']}  scheme_codes={summary['scheme_codes']}  "
               f"sample={summary['sample']}")
    for ac in PRIORITY_SEQUENCE:
        typer.echo(f"  {summary['by_asset_class'][ac]:5d}  {ac}")


@app.command()
def ingest(
    sample: bool = typer.Option(False, "--sample", help="Ingest the 1K stratified sample."),
    all: bool = typer.Option(False, "--all", help="Ingest the full priority-ordered worklist."),
    universe: bool = typer.Option(False, "--universe",
                                  help="Ingest EVERY mfapi scheme (~37.6K, incl. dead/IDCW)."),
    tier: Optional[str] = typer.Option(None, help="Restrict to one asset_class tier."),
    concurrency: int = typer.Option(8, help="Max in-flight requests."),
):
    """Fetch NAV history into the resumable cache."""
    if universe:
        codes = catalog_mod.all_scheme_codes()
    else:
        src = CATALOG_DIR / ("sample_1k.json" if sample else "worklist.json")
        if not src.exists():
            typer.echo("Run `mfrisk catalog` first.")
            raise typer.Exit(1)
        entries = json.loads(src.read_text())
        if sample:  # sample is a fund list; expand to growth codes
            if tier:
                entries = [f for f in entries if f["asset_class"] == tier]
            codes = [c for f in entries
                     for c in (f["direct_growth_code"], f["regular_growth_code"]) if c]
        else:
            if tier:
                entries = [e for e in entries if e["asset_class"] == tier]
            codes = [e["scheme_code"] for e in entries]
    typer.echo(f"ingesting {len(codes)} scheme codes -> {CACHE_DIR} "
               f"(concurrency={concurrency})")
    counts = asyncio.run(fetch_mod.run(codes, CACHE_DIR, concurrency=concurrency))
    typer.echo(f"done: ok={counts['ok']} empty={counts['empty']} skip={counts['skip']} "
               f"error={counts['error']} stuck={counts['stuck']}")
    if counts["stuck"]:
        raise typer.Exit(2)  # signal: back off and retry later


@app.command()
def status():
    """Show catalog + cache progress."""
    wl = CATALOG_DIR / "worklist.json"
    if not wl.exists():
        typer.echo("No catalog yet. Run `mfrisk catalog`.")
        raise typer.Exit()
    worklist = json.loads(wl.read_text())
    cached = {int(p.stem.split(".")[0]) for p in CACHE_DIR.glob("*.json.gz")} \
        if CACHE_DIR.exists() else set()
    by_ac_total: dict[str, int] = {}
    by_ac_done: dict[str, int] = {}
    for e in worklist:
        ac = e["asset_class"]
        by_ac_total[ac] = by_ac_total.get(ac, 0) + 1
        if e["scheme_code"] in cached:
            by_ac_done[ac] = by_ac_done.get(ac, 0) + 1
    typer.echo(f"cache: {len(cached)} / {len(worklist)} scheme codes")
    for ac in PRIORITY_SEQUENCE:
        if ac in by_ac_total:
            typer.echo(f"  {by_ac_done.get(ac, 0):5d} / {by_ac_total[ac]:<5d}  {ac}")


@app.command()
def compute():
    """Compute risk-adjusted metrics from the NAV cache into DuckDB."""
    from . import metrics as metrics_mod
    summary = metrics_mod.compute()
    typer.echo(f"computed funds={summary['funds']}  metric_rows={summary['metric_rows']}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    """Launch the FastAPI + HTMX microsite."""
    import uvicorn
    uvicorn.run("mfrisk.web.app:app", host=host, port=port, log_level="info")


@app.command()
def events():
    """Print the static market-events dictionary."""
    from .data.market_events import events as ev
    for e in ev():
        typer.echo(f"{e['date']}  [{e['category']:<12}] s{e['severity']}  {e['label']}")


if __name__ == "__main__":
    app()
