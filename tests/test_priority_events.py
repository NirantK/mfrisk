"""Priority ordering and the static market-event dictionary."""

from mfrisk import priority as P
from mfrisk.data.market_events import events


def test_priority_is_equity_first_debt_last():
    assert P.rank("equity_domestic") == 0
    assert P.rank("equity_domestic") < P.rank("hybrid") < P.rank("debt") < P.rank("other")


def test_priority_unknown_sorts_last():
    assert P.rank("nonsense") == len(P.PRIORITY_SEQUENCE)


def test_priority_sequence_unique():
    assert len(P.PRIORITY_SEQUENCE) == len(set(P.PRIORITY_SEQUENCE))


def test_events_sorted_and_well_formed():
    evs = events()
    assert len(evs) >= 15
    dates = [e["date"] for e in evs]
    assert dates == sorted(dates)  # chronological
    for e in evs:
        assert set(e) >= {"date", "label", "category", "severity", "note"}
        assert 1 <= e["severity"] <= 3
        assert len(e["date"]) == 10 and e["date"][4] == "-"  # ISO YYYY-MM-DD
