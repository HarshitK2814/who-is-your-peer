"""H3: T_FF49 vs V0_FF49 Sharpe difference (HAC delta method, 6 lags), design period 2012-01..2019-12.
Also the seen-period version, labelled. Run: python scripts/v2/h3_turnover.py"""

import json

import pandas as pd
from common import CHOICE, PERIODS, TAB, hash12, slice_period, v2_returns

from peerrel.stats import sharpe_diff_hac


def main():
    long = v2_returns()
    w = long.pivot(index="date", columns="book", values="excess_ret")
    out = {"prereg_hash": hash12(), "periods": {}}
    for plabel, (lo, hi) in PERIODS.items():
        a, b = slice_period(w["T_FF49"], lo, hi), slice_period(w["V0_FF49"], lo, hi)
        t = sharpe_diff_hac(a, b, periods=12, lags=6)
        g = long.set_index("date")
        row = {k: float(v) for k, v in t.items()}
        for name in ["T_FF49", "V0_FF49"]:
            gg = slice_period(g[g.book == name], lo, hi)
            row[f"{name}_turnover"] = float(gg["turnover"].mean())
            row[f"{name}_cost_bps_yr"] = float(1e4 * 12 * gg["cost"].mean())
            row[f"{name}_fallback_months"] = int(gg["turnover_fallback"].sum())
        out["periods"][plabel] = row
    d = out["periods"]["design 2012-2019 (choice period)"]
    out["H3_supported"] = bool(d["diff_ann"] > 0 and d["p_two_sided"] < 0.05)
    (TAB / "h3_turnover.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
