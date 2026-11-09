"""With all v2 options off the v2 runner must reproduce the sealed v1 C_FF49 returns (first months).
Needs the git-ignored data; skips itself on a fresh clone."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "results" / "runs" / "20260926-1702_full_main" / "returns.parquet"
PANEL = ROOT / "data" / "processed" / "panel.parquet"
pytestmark = pytest.mark.skipif(not (V1.exists() and PANEL.exists()), reason="needs local data")


def test_parity_first_three_months():
    sys.path.insert(0, str(ROOT / "scripts" / "v2"))
    from common import CFG, load_bt, signal_dates
    from peerrel.v2 import styledata
    from peerrel.v2.runner import SPECS, BacktestV2

    bt0, panel = load_bt()
    bt = BacktestV2(bt0.panel, bt0.daily_ret, bt0.ffd, bt0.ffm, bt0.months.reset_index(), bt0.static_groups, bt0.opt, bt0.cfg)
    table, hist = styledata.load_or_build(ROOT, panel, bt.daily_ret, bt.ffd["Mkt-RF"], bt.months.reset_index(),
                                          bt.static_groups["FF49"], bt.cfg)
    dates = signal_dates(panel, "2012-01-01", "2012-03-31")
    import tempfile
    res = bt.run_v2(dates, Path(tempfile.mkdtemp()), {"P_FF49": SPECS["P_FF49"]}, CFG["v2"], table, hist)
    v1 = pd.read_parquet(V1)
    v1 = v1[v1.book == "C_FF49"].set_index("date").loc[dates]
    got = res.set_index("date")
    assert (got["excess_ret"] - v1["excess_ret"]).abs().max() < 5e-5
    assert (got["turnover"] - v1["turnover"]).abs().max() < 5e-4
