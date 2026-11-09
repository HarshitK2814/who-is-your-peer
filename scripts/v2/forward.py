"""P1 v2 forward paper tracker (the only unseen-data test). Books: V0_FF49, SIN_FF49 and P_FF49 (= v1 C_FF49 spec).
Signal at month-end t (data <= t), fill at the t+1 close, hold to the next month's t+1 close. The paper path starts FLAT
at the first forward signal month (2026-11), so it never depends on seen-period history. For every forward month the
target weights are written once to results/v2/forward/weights_YYYY-MM.csv (commit them at once: the git timestamp is the
proof the weights preceded the outcome); realised net returns are appended to forward.csv when the next month's data
exist. Costs: v1 half-spread + square-root impact at $100M NAV, tiered borrow (assumption), no capacity beyond $100M.
Usage: python scripts/v2/forward.py [--refresh]   (--refresh re-runs download+build first; needs the SEC User-Agent in .env)"""

import sys
from pathlib import Path

import pandas as pd
from common import CFG, PREREG, ROOT, SPLITS, hash12, load_bt

from peerrel.v2 import styledata
from peerrel.v2.forward_log import append_new, forward_dates, pending_flags
from peerrel.v2.runner import SPECS, BacktestV2
from qcore.splits import guard

OUT = ROOT / "results" / "v2" / "forward"
BOOKS = ["P_FF49", "V0_FF49", "SIN_FF49"]


def main(refresh: bool = False) -> int:
    if refresh:
        import run as v1run                      # scripts/run.py (v1 pipeline)
        v1run.step_download()
        v1run.step_build()
    guard("forward", PREREG)
    bt0, panel = load_bt()
    all_dates = panel.index.get_level_values("date").unique()
    months = forward_dates(all_dates, SPLITS)
    if not months:
        print(f"no forward signal months yet (panel ends {all_dates.max().date()}; forward starts {SPLITS.forward[0]})")
        return 0
    bt = BacktestV2(bt0.panel, bt0.daily_ret, bt0.ffd, bt0.ffm, bt0.months.reset_index(), bt0.static_groups, bt0.opt, bt0.cfg)
    table, hist = styledata.load_or_build(ROOT, panel, bt.daily_ret, bt.ffd["Mkt-RF"], bt.months.reset_index(),
                                          bt.static_groups["FF49"], bt.cfg, force=refresh)
    has_out = panel["ret_fwd"].notna().groupby(level="date").any().to_dict()
    res = bt.run_v2(months, OUT / "_run", {b: SPECS[b] for b in BOOKS}, CFG["v2"], table, hist)
    W = pd.read_parquet(OUT / "_run" / "weights.parquet")
    pend = pending_flags(months, has_out)
    OUT.mkdir(parents=True, exist_ok=True)
    for t in months:
        f = OUT / f"weights_{t:%Y-%m}.csv"
        if not f.exists():
            W[W.date == t].to_csv(f, index=False)
    done = res[[not pend[d] for d in res["date"]]]
    rows = pd.DataFrame({"date": done["date"], "book": done["book"], "net_return": done["excess_ret"], "prereg_hash": hash12()})
    n_new = append_new(OUT / "forward.csv", rows)
    n_m = rows["date"].nunique()
    print(f"forward months with weights: {len(months)}; with outcomes: {n_m}; new rows: {n_new}")
    return n_m


if __name__ == "__main__":
    main("--refresh" in sys.argv)
