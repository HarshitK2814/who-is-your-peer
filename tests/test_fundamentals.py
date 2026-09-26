"""Point-in-time correctness of the XBRL fundamentals engine (synthetic filings)."""

import numpy as np
import pandas as pd
import pytest

from peerrel.data.xbrl import first_reported
from peerrel.features.fundamentals import discrete_quarters, month_key, point_in_time, ttm


def _fact(concept, start, end, val, filed, cik=1):
    return {"cik": cik, "concept": concept, "priority": 0, "start": start, "end": end, "val": val,
            "filed": filed, "form": "10-Q", "accn": filed, "fy": 2019, "fp": "Q"}


@pytest.fixture
def ytd_cashflows():
    """CFO reported year-to-date, as cash-flow statements are in 10-Qs: 10, 25, 45, 70."""
    rows = [
        _fact("cfo", "2019-01-01", "2019-03-31", 10, "2019-05-10"),
        _fact("cfo", "2019-01-01", "2019-06-30", 25, "2019-08-10"),
        _fact("cfo", "2019-01-01", "2019-09-30", 45, "2019-11-10"),
        _fact("cfo", "2019-01-01", "2019-12-31", 70, "2020-02-20"),
        # a later 10-K restates FY2019 — must be ignored (as-first-reported)
        _fact("cfo", "2019-01-01", "2019-12-31", 99, "2021-02-20"),
    ]
    return first_reported(pd.DataFrame(rows))


def test_restatement_ignored(ytd_cashflows):
    fy = ytd_cashflows[ytd_cashflows["end"] == "2019-12-31"]
    assert fy["val"].tolist() == [70]


def test_discrete_quarters_from_ytd(ytd_cashflows):
    q = discrete_quarters(ytd_cashflows).sort_values("m")
    assert q["val"].tolist() == [10, 15, 20, 25]
    # Q4 = FY - 9M is only known once the 10-K is filed
    assert q["avail"].iloc[-1] == pd.Timestamp("2020-02-20")


def test_ttm_uses_annual_and_availability(ytd_cashflows):
    q = discrete_quarters(ytd_cashflows)
    t = ttm(ytd_cashflows, q)
    row = t[t["m"] == month_key(pd.Series([pd.Timestamp("2019-12-31")]))[0]]
    assert row["val"].item() == 70
    assert row["avail"].item() == pd.Timestamp("2020-02-20")


def test_52_53_week_year_ends_share_a_month_key():
    ends = pd.Series(pd.to_datetime(["2019-09-28", "2019-09-30", "2019-10-02"]))
    assert month_key(ends).nunique() == 1


def test_point_in_time_never_uses_future_filings():
    period = pd.DataFrame({
        "x": [1.0, 2.0],
        "avail_x": pd.to_datetime(["2020-02-20", "2020-03-31"]),
    }, index=pd.MultiIndex.from_tuples([(1, 2019 * 12 + 11), (1, 2020 * 12 + 2)], names=["cik", "m"]))
    grid = pd.DatetimeIndex(["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"])
    pit = point_in_time(period, grid)["x"].droplevel("cik")
    assert np.isnan(pit.loc["2020-01-31"])       # not filed yet
    assert pit.loc["2020-02-29"] == 1.0           # filed 20 Feb
    assert pit.loc["2020-03-31"] == 1.0           # filed ON the month-end: usable only next day
    assert pit.loc["2020-04-30"] == 2.0


def test_point_in_time_ignores_late_filed_older_period():
    """An amendment for an OLD period filed later must not replace a newer period."""
    period = pd.DataFrame({
        "x": [5.0, 7.0],
        "avail_x": pd.to_datetime(["2020-05-10", "2020-06-15"]),
    }, index=pd.MultiIndex.from_tuples([(1, 2020 * 12 + 2), (1, 2019 * 12 + 11)], names=["cik", "m"]))
    pit = point_in_time(period, pd.DatetimeIndex(["2020-06-30"]))["x"]
    assert pit.item() == 5.0


def test_stale_values_expire():
    period = pd.DataFrame({"x": [1.0], "avail_x": pd.to_datetime(["2018-02-20"])},
                          index=pd.MultiIndex.from_tuples([(1, 2017 * 12 + 11)], names=["cik", "m"]))
    pit = point_in_time(period, pd.DatetimeIndex(["2018-03-31", "2019-12-31"]))["x"].droplevel("cik")
    assert pit.loc["2018-03-31"] == 1.0
    assert np.isnan(pit.loc["2019-12-31"])
