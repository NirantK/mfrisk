"""Shared test fixtures — synthetic NAV frames with known properties."""

from datetime import date, timedelta

import polars as pl
import pytest


@pytest.fixture
def build_daily():
    """Build a daily (date, nav) frame from a list of NAVs."""
    def _b(navs, start=date(2018, 1, 1)):
        dates = [start + timedelta(days=i) for i in range(len(navs))]
        return pl.DataFrame({"date": dates, "nav": [float(x) for x in navs]}).sort("date")
    return _b


@pytest.fixture
def span_frame():
    """A 2-point frame spanning `years` (enough to test coverage/plan rules)."""
    def _s(years):
        end = date(2026, 1, 1)
        start = end - timedelta(days=int(years * 365.25))
        return pl.DataFrame({"date": [start, end], "nav": [100.0, 200.0]})
    return _s
