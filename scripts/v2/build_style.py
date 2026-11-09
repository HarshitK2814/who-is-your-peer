"""Build the cached style-model inputs (infrastructure; computes no hypothesis statistic).
Usage: python scripts/v2/build_style.py [--force]"""

import sys
import time

from common import ROOT, load_bt

from peerrel.v2 import styledata

if __name__ == "__main__":
    t0 = time.time()
    bt, panel = load_bt()
    ind49 = bt.static_groups["FF49"]
    table, hist = styledata.load_or_build(ROOT, panel, bt.daily_ret, bt.ffd["Mkt-RF"],
                                          bt.months.reset_index(), ind49, bt.cfg, force="--force" in sys.argv)
    print(table.shape, hist.fret.shape, hist.resid.shape, f"{time.time() - t0:.0f}s")
    print(hist.fret.index.min(), hist.fret.index.max(), table["date"].min(), table["date"].max())
