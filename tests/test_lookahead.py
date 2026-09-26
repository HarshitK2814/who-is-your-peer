"""Shift test: perturbing any data AFTER month-end t must not change features at t.
Only `ret_fwd` (the outcome) is allowed to change."""

import numpy as np
import pandas as pd

from peerrel.features.panel import market_features, month_end_map, trading_calendar


def _synthetic_prices(seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-01", "2020-06-30")
    rows = []
    for tk in ["AAA", "BBB", "CCC"]:
        r = rng.normal(0.0004, 0.02, len(dates))
        close = 50 * np.exp(np.cumsum(r))
        rows.append(pd.DataFrame({
            "date": dates, "ticker": tk, "close": close, "adj_close": close * 1.0,
            "high": close * (1 + rng.uniform(0, 0.02, len(dates))),
            "low": close * (1 - rng.uniform(0, 0.02, len(dates))),
            "raw_close": close, "split_factor_after": 1.0,
            "dollar_volume": close * 1e6, "volume": 1e6,
        }))
    px = pd.concat(rows, ignore_index=True)
    px["ret"] = px.groupby("ticker")["adj_close"].pct_change()
    return px


def test_market_features_do_not_look_ahead():
    px = _synthetic_prices()
    months = month_end_map(trading_calendar(px), "2019-01-31", "2020-05-31")
    base = market_features(px, months)
    cut = pd.Timestamp("2019-09-30")
    shocked = px.copy()
    after = shocked["date"] > cut
    ramp = 1.0 + (shocked.loc[after, "date"] - cut).dt.days / 30.0   # time-varying, so ratios change
    for col in ["close", "adj_close", "high", "low", "raw_close"]:
        shocked.loc[after, col] *= ramp
    shocked["ret"] = shocked.groupby("ticker")["adj_close"].pct_change()
    shocked.loc[after, "dollar_volume"] *= 10
    new = market_features(shocked, months)

    upto = base.index.get_level_values("date") <= cut
    feature_cols = [c for c in base.columns if c != "ret_fwd"]
    pd.testing.assert_frame_equal(base.loc[upto, feature_cols], new.loc[upto, feature_cols])
    # the outcome for the last pre-cut signal date legitimately changes
    assert not np.allclose(base.loc[(cut, "AAA"), "ret_fwd"], new.loc[(cut, "AAA"), "ret_fwd"])


def test_execution_is_after_signal_bar():
    px = _synthetic_prices()
    m = month_end_map(trading_calendar(px), "2019-01-31", "2020-05-31")
    assert (m["exec_day"] > m["date"]).all()
    assert (m["signal_day"] <= m["date"]).all()
