"""Run the v2 books (and the parity book) month by month, 2012-01 .. latest month with an outcome.
One continuous run, as in v1; periods are sliced afterwards (design period vs seen period).
Usage: python scripts/v2/run_books.py [--books V0_FF49 ...] [--end 2012-03] [--tag name]"""

import argparse

from common import CFG, RUNS, ROOT, hash12, load_bt, signal_dates

from peerrel.v2 import styledata
from peerrel.v2.runner import NEW_BOOKS, SPECS, BacktestV2

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", nargs="*", default=["P_FF49"] + NEW_BOOKS)
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--tag", default="v2_main")
    a = ap.parse_args()
    bt0, panel = load_bt()
    bt = BacktestV2(bt0.panel, bt0.daily_ret, bt0.ffd, bt0.ffm, bt0.months.reset_index(), bt0.static_groups, bt0.opt, bt0.cfg)
    table, hist = styledata.load_or_build(ROOT, panel, bt.daily_ret, bt.ffd["Mkt-RF"], bt.months.reset_index(),
                                          bt.static_groups["FF49"], bt.cfg)
    dates = signal_dates(panel, a.start, a.end)
    out = RUNS / a.tag
    bt.run_v2(dates, out, {b: SPECS[b] for b in a.books}, CFG["v2"], table, hist)
    print("run:", out, "prereg", hash12())
