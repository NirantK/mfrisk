"""Classification, plan detection, and fund-grouping tests."""

import pytest

from mfrisk import catalog as C


@pytest.mark.parametrize("category,name,expected", [
    ("Equity Scheme - Large Cap Fund", "SBI Large Cap Direct Growth", "equity_domestic"),
    ("Equity Scheme - Sectoral/ Thematic", "Mirae Asset NYSE FANG+ ETF", "equity_global"),
    ("Other Scheme - FoF Overseas", "Edelweiss Greater China Equity Off-shore", "equity_global"),
    ("Other Scheme - Index Funds", "Motilal Oswal Nasdaq 100 Index Fund", "equity_passive"),
    ("Other Scheme - Index Funds", "Edelweiss CRISIL IBX 50:50 Gilt Plus SDL Index", "debt"),
    ("Other Scheme - Gold ETF", "Nippon India Gold ETF", "commodity"),
    ("Hybrid Scheme - Multi Asset Allocation", "ICICI Multi Asset Fund", "hybrid_multiasset"),
    ("Hybrid Scheme - Arbitrage Fund", "Kotak Arbitrage Fund", "hybrid_arbitrage"),
    ("Hybrid Scheme - Aggressive Hybrid Fund", "SBI Equity Hybrid Fund", "hybrid"),
    ("Debt Scheme - Liquid Fund", "Axis Liquid Fund", "debt"),
    ("Solution Oriented Scheme - Retirement Fund", "HDFC Retirement Fund", "solution"),
])
def test_asset_class(category, name, expected):
    assert C.asset_class(category, name) == expected


def test_is_growth():
    assert C.is_growth("SBI Large Cap Fund - Direct Plan - Growth")
    assert not C.is_growth("SBI Large Cap Fund - Direct Plan - IDCW")
    assert not C.is_growth("SBI Large Cap Fund - Growth - Dividend Payout")
    assert not C.is_growth("SBI Large Cap Fund - Bonus Option")


def test_is_direct():
    assert C.is_direct("HDFC Flexi Cap - Direct Plan - Growth")
    assert not C.is_direct("HDFC Flexi Cap - Regular Plan - Growth")


def test_base_name_groups_direct_and_regular():
    # Direct and Regular Growth plans of one fund must collapse to one key
    direct = C.base_name("SBI Large Cap Fund - Direct Plan - Growth")
    regular = C.base_name("SBI Large Cap Fund - Regular Plan - Growth")
    assert direct == regular == "sbi large cap fund"
