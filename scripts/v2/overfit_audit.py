"""H4: overfitting audit of the v1 book family on the design period 2012-01..2019-12 (96 months).
PBO via CSCV (8 blocks of 12 months) < 0.5 and deflated Sharpe of v1 C_FF49 (n_trials = 17) > 0.90.
Run: python scripts/v2/overfit_audit.py"""

import json

import matplotlib
import numpy as np
import pandas as pd
from common import CHOICE, FIG, TAB, hash12, sharpe_ci, slice_period, v1_returns, v2_wide

from qcore.validation import deflated_sharpe, expected_max_sharpe, pbo_cscv, probabilistic_sharpe

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

V1 = "C_FF49"


def sh_m(r) -> float:
    r = pd.Series(r)
    return float(r.mean() / r.std(ddof=1))


def main():
    lo, hi = CHOICE
    M = slice_period(v1_returns(), lo, hi)
    assert M.shape == (96, 17) and not M.isna().any().any()
    sr = M.apply(sh_m)
    sr_var = float(sr.var(ddof=1))
    pbo = pbo_cscv(M, n_blocks=8)
    dsr = deflated_sharpe(M[V1], 17, sr_var)
    new = slice_period(v2_wide(), lo, hi)[["V0_FF49", "SN_FF49", "SIN_FF49", "T_FF49", "TSIN_FF49"]]
    M22 = pd.concat([M, new], axis=1).dropna()
    sr22 = M22.apply(sh_m)
    pbo22 = pbo_cscv(M22, n_blocks=8)
    sens = {str(n): float(deflated_sharpe(M[V1], n, sr_var)) for n in (17, 22, 68)}
    s, a, c = sharpe_ci(M[V1])
    best = sr.idxmax()
    out = {
        "prereg_hash": hash12(), "period": [lo, hi], "n_months": int(len(M)), "n_trials": 17,
        "pbo": pbo["pbo"], "pbo_n_combinations": pbo["n_combinations"], "pbo_logit_median": float(np.median(pbo["logits"])),
        "sr_var_per_month": sr_var, "expected_max_sharpe_ann": expected_max_sharpe(17, sr_var) * np.sqrt(12),
        "v1_C_FF49_sharpe": s, "v1_C_FF49_ci95": [a, c], "v1_C_FF49_psr_vs_0": probabilistic_sharpe(M[V1], 0.0),
        "v1_C_FF49_dsr": dsr, "best_book_in_sample": best, "best_book_ann_sharpe": float(sr[best] * np.sqrt(12)),
        "n_books_sharpe_gt_0": int((sr > 0).sum()),
        "dsr_sensitivity_by_n_trials": sens,
        "with_new_books": {"n_columns": int(M22.shape[1]), "pbo": pbo22["pbo"],
                           "best_book": sr22.idxmax(), "best_ann_sharpe": float(sr22.max() * np.sqrt(12))},
        "H4": {"pbo_lt_0.5": bool(pbo["pbo"] < 0.5), "dsr_gt_0.90": bool(dsr > 0.90),
               "supported": bool(pbo["pbo"] < 0.5 and dsr > 0.90)},
    }
    (TAB / "overfit_audit.json").write_text(json.dumps(out, indent=1, default=float))
    (sr * np.sqrt(12)).rename("ann_sharpe").to_csv(TAB / "overfit_family_sharpe.csv")
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.hist(pbo["logits"], bins=30, color="#4477aa")
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel("logit of out-of-sample rank of the in-sample best book")
    ax.set_ylabel("CSCV combinations")
    ax.set_title(f"v1 17 books, design period 2012-2019: PBO = {pbo['pbo']:.2f}")
    fig.tight_layout()
    fig.savefig(FIG / "pbo_logits.png", dpi=130)
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
