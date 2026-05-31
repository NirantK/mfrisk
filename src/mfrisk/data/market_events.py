"""Static dictionary of major events that materially moved Indian markets.

Hand-curated seed, version-controlled. Dates are the primary impact day (or the
start of a multi-day episode). Used to overlay vertical markers on NAV charts and
to contextualize drawdowns in fund detail / compare views.

Schema per event:
    date     : ISO "YYYY-MM-DD" — primary impact day / episode start.
    label    : short chart label.
    category : one of {crash, policy, global, geopolitical, sector, pandemic}.
    severity : 1 (notable) .. 3 (severe, broad market).
    note     : one-line context.

Curation rules:
    - India-relevant only (global events included when they hit Indian indices).
    - Prefer the actual market-impact date over the news date when they differ.
    - Keep it tight; this is signal, not a news log. Extend via web research.

Seed compiled 2026-05-31 from public market-history sources (Wikipedia "Stock
market crashes in India" and contemporaneous reporting). Verify before relying
on any single date for analysis.
"""

from __future__ import annotations

from typing import TypedDict


class MarketEvent(TypedDict):
    date: str
    label: str
    category: str
    severity: int
    note: str


MARKET_EVENTS: list[MarketEvent] = [
    {
        "date": "1992-04-29",
        "label": "Harshad Mehta scam",
        "category": "crash",
        "severity": 3,
        "note": "Securities scam unwinds; Sensex collapses through 1992.",
    },
    {
        "date": "2000-03-13",
        "label": "Dot-com bust",
        "category": "crash",
        "severity": 3,
        "note": "Global tech bubble burst drags Indian IT through 2000-01.",
    },
    {
        "date": "2001-03-02",
        "label": "Ketan Parekh scam",
        "category": "crash",
        "severity": 2,
        "note": "Payment crisis / KP scam; markets slide amid dot-com fallout.",
    },
    {
        "date": "2004-05-17",
        "label": "Election shock",
        "category": "policy",
        "severity": 2,
        "note": "Surprise UPA win; Sensex hits lower circuit, ~11% intraday fall.",
    },
    {
        "date": "2006-05-22",
        "label": "May 2006 correction",
        "category": "crash",
        "severity": 2,
        "note": "Sharp global EM sell-off; Sensex falls steeply from highs.",
    },
    {
        "date": "2008-01-21",
        "label": "GFC sell-off begins",
        "category": "crash",
        "severity": 3,
        "note": "Subprime crisis; Sensex two-day crash, circuit breakers hit.",
    },
    {
        "date": "2008-10-24",
        "label": "GFC trough",
        "category": "crash",
        "severity": 3,
        "note": "Lehman aftermath; Sensex down ~60% from 2008 peak.",
    },
    {
        "date": "2011-08-08",
        "label": "US downgrade / Eurozone",
        "category": "global",
        "severity": 2,
        "note": "S&P cuts US rating; euro-debt fears; global risk-off.",
    },
    {
        "date": "2013-08-16",
        "label": "Taper tantrum",
        "category": "global",
        "severity": 2,
        "note": "Fed taper signals; INR slumps to record low, equities fall.",
    },
    {
        "date": "2015-08-24",
        "label": "China devaluation",
        "category": "global",
        "severity": 2,
        "note": "Yuan devaluation; Sensex crashes 1,624 pts on China slowdown.",
    },
    {
        "date": "2016-11-09",
        "label": "Demonetisation",
        "category": "policy",
        "severity": 2,
        "note": "Note ban announced 8 Nov; markets drop, Sensex -6% intraday.",
    },
    {
        "date": "2018-02-02",
        "label": "LTCG tax / vol spike",
        "category": "policy",
        "severity": 1,
        "note": "Budget reintroduces LTCG on equities; global vol (VIX) spike.",
    },
    {
        "date": "2018-09-21",
        "label": "IL&FS / NBFC crisis",
        "category": "sector",
        "severity": 2,
        "note": "IL&FS defaults trigger NBFC liquidity crunch; financials slump.",
    },
    {
        "date": "2020-03-23",
        "label": "COVID-19 crash",
        "category": "pandemic",
        "severity": 3,
        "note": "Pandemic low; Sensex -13% single day, ~38% drawdown off Jan peak.",
    },
    {
        "date": "2022-02-24",
        "label": "Russia-Ukraine war",
        "category": "geopolitical",
        "severity": 2,
        "note": "Invasion; oil spike, global risk-off, Indian equities fall.",
    },
    {
        "date": "2022-06-16",
        "label": "Fed rate-hike sell-off",
        "category": "global",
        "severity": 2,
        "note": "Aggressive Fed tightening; 2022 global equity bear market.",
    },
    {
        "date": "2023-01-24",
        "label": "Adani-Hindenburg",
        "category": "sector",
        "severity": 2,
        "note": "Hindenburg report; Adani stocks lose ~$140bn over weeks.",
    },
    {
        "date": "2024-06-04",
        "label": "2024 election result",
        "category": "policy",
        "severity": 2,
        "note": "Narrower NDA majority vs exit polls; Sensex -4,390 pts intraday.",
    },
    {
        "date": "2024-08-05",
        "label": "Yen carry-trade unwind",
        "category": "global",
        "severity": 2,
        "note": "BoJ hike + weak US jobs; Nikkei -12%, global selloff hits India.",
    },
]


def events() -> list[MarketEvent]:
    """Return the static event list (chronological)."""
    return sorted(MARKET_EVENTS, key=lambda e: e["date"])
