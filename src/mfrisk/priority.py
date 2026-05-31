"""The written ingest priority sequence — single source of truth.

Order is equity-first, liquid-debt-last. `catalog.py` assigns each canonical
fund an ``asset_class`` from this set; the runner walks tiers in this order.
"""

from __future__ import annotations

# Ordered: index 0 = highest priority.
PRIORITY_SEQUENCE: list[str] = [
    "equity_domestic",   # Large/Mid/Small/Flexi/Multi/Focused/Value/Contra/DivYield/ELSS/Sectoral
    "equity_global",     # FoF Overseas + global equity (Nasdaq, S&P, China, US, Japan, EM)
    "equity_passive",    # domestic equity index funds + equity ETFs
    "hybrid",            # Aggressive Hybrid, BAF/Dynamic AA, Equity Savings, Conservative, Balanced
    "hybrid_multiasset", # Multi Asset Allocation
    "hybrid_arbitrage",  # Arbitrage
    "solution",          # Retirement, Children's
    "commodity",         # Gold / Silver ETF & FoF
    "debt",              # Liquid -> Ultra/Short -> Corp/Credit -> Gilt/Long -> target-maturity index
    "other",             # IDF, close-ended income/growth, interval, unclassified
]

PRIORITY_RANK: dict[str, int] = {ac: i for i, ac in enumerate(PRIORITY_SEQUENCE)}


def rank(asset_class: str) -> int:
    """Priority index for an asset class (unknown classes sort last)."""
    return PRIORITY_RANK.get(asset_class, len(PRIORITY_SEQUENCE))
