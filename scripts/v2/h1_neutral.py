"""H1 (preregistration_v2.md): does the industry+style-neutral composite earn a positive net excess return?
Design period 2012-01..2019-12. One-sided Romano-Wolf stepdown over {SN_FF49, SIN_FF49, TSIN_FF49}.
Also writes the per-book table (design and seen period) and FF5+UMD spanning alphas.
Run: python scripts/v2/h1_neutral.py"""

import json

import pandas as pd
from common import CHOICE, PERIODS, ROOT, TAB, hash12, sharpe_ci, slice_period, v1_returns, v2_returns, v2_wide

from peerrel.data.french import factors
from peerrel.stats import romano_wolf, spanning
from peerrel.v2.stylemodel import STYLES

BOOKS = ["V0_FF49", "SN_FF49", "SIN_FF49", "T_FF49", "TSIN_FF49"]


def main():
    long = v2_returns()
    v1 = v1_returns()
    wide = long.pivot(index="date", columns="book", values="excess_ret")
    rows = []
    for plabel, (lo, hi) in PERIODS.items():
        for b in ["v1_C_FF49", "P_FF49"] + BOOKS:
            if b == "v1_C_FF49":
                r = slice_period(v1["C_FF49"], lo, hi)
                g = None
            else:
                r = slice_period(wide[b], lo, hi)
                g = slice_period(long[long.book == b].set_index("date"), lo, hi)
            s, a, c = sharpe_ci(r)
            row = {"book": b, "period": plabel, "months": len(r), "mean_excess_ann_pct": 1200 * r.mean(),
                   "sharpe": s, "ci_lo": a, "ci_hi": c}
            if g is not None:
                row.update({"turnover_oneway_per_month": g["turnover"].mean(), "cost_bps_yr": 1e4 * 12 * g["cost"].mean(),
                            "borrow_bps_yr": 1e4 * 12 * g["borrow"].mean(), "gross_exposure": g["gross_exposure"].mean(),
                            "max_abs_style_expo": g[[f"expo_{k}" for k in STYLES]].abs().max().max(),
                            "turnover_fallback_months": int(g["turnover_fallback"].sum()), "opt_failed_months": int(g["opt_failed"].sum())})
            rows.append(row)
    pd.DataFrame(rows).to_csv(TAB / "book_stats.csv", index=False)

    lo, hi = CHOICE
    new = ["SN_FF49", "SIN_FF49", "TSIN_FF49"]
    des = slice_period(wide[new], lo, hi)
    rw = romano_wolf(des, n_boot=5000, mean_block=6.0, seed=0)
    ext_cols = {f"v1_B_{s}": slice_period(v1[f"B_{s}"], lo, hi) for s in ["FF12", "FF49", "SIC3", "RCLUST"]}
    ext = pd.concat([pd.DataFrame(ext_cols), des], axis=1).dropna()
    rw_ext = romano_wolf(ext, n_boot=5000, mean_block=6.0, seed=0)
    ci = {b: sharpe_ci(des[b]) for b in new}
    ffm = factors(daily=False)
    span = {}
    for b in ["V0_FF49", "SN_FF49", "SIN_FF49"]:
        sp = spanning(slice_period(wide[b], lo, hi) , ffm[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]])
        span[b] = {k: float(v) for k, v in sp.items()}
    out = {
        "prereg_hash": hash12(), "period": [lo, hi], "n_months": int(len(des)),
        "rw": {b: {"t": float(rw.loc[b, "t_stat"]), "p_rw": float(rw.loc[b, "p_rw"]),
                   "sharpe": ci[b][0], "ci95": [ci[b][1], ci[b][2]]} for b in new},
        "rw_extended_v1_B_plus_new": {b: {"t": float(rw_ext.loc[b, "t_stat"]), "p_rw": float(rw_ext.loc[b, "p_rw"])} for b in rw_ext.index},
        "H1_supported": bool(rw.loc["SIN_FF49", "p_rw"] < 0.05),
        "spanning_FF5_UMD": span,
    }
    (TAB / "h1_neutral.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
