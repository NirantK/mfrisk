"""Metric-math characterization tests — synthetic series with known answers."""

from mfrisk import metrics as M


def test_clean_jumps_truncates_after_last_artifact(build_daily):
    # a 100x face-value reset mid-series -> keep only the clean post-jump segment
    navs = [10.0, 10.1, 10.05, 1005.0, 1006.0, 1007.0, 1008.0]
    df = build_daily(navs)
    cleaned = M.clean_jumps(df)
    assert cleaned.height == 3  # only the three post-jump rows survive
    assert cleaned["nav"].to_list() == [1006.0, 1007.0, 1008.0]


def test_clean_jumps_noop_on_clean_series(build_daily):
    df = build_daily([100, 101, 102, 103])
    assert M.clean_jumps(df).height == 4


def test_monotonic_up_has_zero_pain(build_daily):
    # strictly rising NAV over a year -> no drawdown at all
    navs = [100.0 * (1.0005 ** i) for i in range(400)]
    m = M.window_metrics(build_daily(navs), 1)
    assert m is not None
    assert m["ulcer_index"] < 1e-9   # never below a running peak
    assert m["max_drawdown"] == 0.0
    assert m["martin"] is None       # ulcer is zero -> guarded
    assert m["sortino"] > 0          # strong positive risk-adjusted return
    assert m["cagr"] > 0


def test_known_max_drawdown(build_daily):
    # flat at 100, then a clean -20% trough, then recovery — all inside 1Y window
    navs = [100.0] * 300 + [80.0] * 20 + [110.0] * 80
    m = M.window_metrics(build_daily(navs), 1)
    assert m is not None
    assert abs(m["max_drawdown"] - (-0.20)) < 1e-9
    assert m["ulcer_index"] > 0


def test_too_short_window_returns_none(build_daily):
    # ~3 months of data cannot fill a 1Y window
    m = M.window_metrics(build_daily([100 + i for i in range(90)]), 1)
    assert m is None


def test_pick_series_plan_resolution(span_frame):
    direct = span_frame(5)      # Direct plan, 5y of history
    regular = span_frame(15)    # Regular plan, 15y of history

    assert M.pick_series(direct, regular, 5)[1] == "direct"     # <=10y, Direct covers
    assert M.pick_series(direct, regular, 10)[1] == "regular"   # Direct too short -> Regular
    assert M.pick_series(direct, regular, 20)[1] == "regular"   # >10y always Regular
    assert M.pick_series(None, regular, 5)[1] == "regular"      # no Direct -> Regular
    assert M.pick_series(direct, None, 20)[1] == "direct"       # only Direct available
    assert M.pick_series(None, None, 5) == (None, None)


def test_spark_values_compact(build_daily):
    df = build_daily([100 + i * 0.1 for i in range(900)])  # ~30 months
    spark = M.spark_values(None, df)
    pts = spark.split(";")
    assert 3 <= len(pts) <= 60
    assert all(float(p) > 0 for p in pts)


def test_spark_values_none_when_no_series():
    assert M.spark_values(None, None) is None
