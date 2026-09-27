"""Pre-registered robustness table: key books and hypothesis statistics per variant, test and full periods."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from qcore import metrics  # noqa: E402

from peerrel.config import RESULTS  # noqa: E402
from peerrel.stats import romano_wolf, sharpe_diff_hac  # noqa: E402

VARIANTS = {"main": "full_main", "cost_x2": "robust_cost2x", "universe_500": "robust_univ500",
            "no_momentum": "robust_nomom"}
PERIODS = {"test": ("2020-01-01", "2023-12-31"), "full": ("2012-01-01", "2026-12-31")}


def main() -> None:
    runs = RESULTS / "runs"
    for pname, (lo, hi) in PERIODS.items():
        rows = {}
        for vname, tag in VARIANTS.items():
            d = sorted(runs.glob(f"*_{tag}"))[-1]
            r = pd.read_parquet(d / "returns.parquet")
            w = r.pivot(index="date", columns="book", values="excess_ret").loc[lo:hi]
            row = {f"sharpe_{b}": metrics.sharpe(w[b], 12) for b in ["C_ALL", "C_FF49", "CN_FF49", "W_FF49", "B_FF49"]}
            rw = romano_wolf(w[[f"B_{s}" for s in ["FF12", "FF49", "SIC3", "RCLUST"]]], n_boot=2000)
            row["H1_min_p_romano_wolf"] = rw["p_rw"].min()
            row["H2_sic3_minus_ff49"] = sharpe_diff_hac(w["C_SIC3"], w["C_FF49"])["diff_ann"]
            row["H2_rclust_minus_ff49"] = sharpe_diff_hac(w["C_RCLUST"], w["C_FF49"])["diff_ann"]
            h3 = sharpe_diff_hac(w["CN_FF49"], w["C_FF49"])
            row["H3_cn_minus_c_ff49"], row["H3_p"] = h3["diff_ann"], h3["p_two_sided"]
            row["avg_cost_ann_C_FF49"] = r[r["book"] == "C_FF49"].set_index("date").loc[lo:hi, "cost"].mean() * 12
            row["n_months"] = len(w)
            rows[vname] = row
        out = pd.DataFrame(rows).T
        out.to_csv(RESULTS / "tables" / f"robustness_{pname}.csv")
        with pd.option_context("display.width", 250, "display.float_format", "{:.3f}".format):
            print(pname)
            print(out)


if __name__ == "__main__":
    main()
