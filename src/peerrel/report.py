"""Tables and figures for a backtest run.

    python -m peerrel.report <run_dir> [<run_dir> ...] --label validation

Every Sharpe is reported with a 95% CI and the number of monthly rebalances. Every
return number is net of the modelled spread + impact costs and a 25 bp/yr borrow fee,
at a $100M capacity assumption, unless a column says 'gross'.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from qcore import metrics  # noqa: E402

from peerrel.config import RESULTS  # noqa: E402
from peerrel.data.french import factors  # noqa: E402
from peerrel.stats import romano_wolf, sharpe_diff_hac, spanning  # noqa: E402

SCHEMES = ["FF12", "FF49", "SIC3", "RCLUST"]


def load_runs(run_dirs: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rets = pd.concat([pd.read_parquet(d / "returns.parquet") for d in run_dirs])
    ics = [pd.read_parquet(d / "ic.parquet") for d in run_dirs if (d / "ic.parquet").exists()]
    rets = rets.drop_duplicates(["date", "book"], keep="last")
    return rets, (pd.concat(ics) if ics else pd.DataFrame())


def book_summary(rets: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for b, g in rets.groupby("book"):
        r = g.set_index("date")["excess_ret"].sort_index()
        s = metrics.summary(r, 12)
        s["gross_sharpe"] = metrics.sharpe(g.set_index("date")["gross_ret"] - g.set_index("date")["net_dollar"] * g.set_index("date")["rf"].fillna(0), 12)
        s["avg_turnover"] = g["turnover"].mean()
        s["avg_cost_ann"] = g["cost"].mean() * 12
        s["avg_gross_exposure"] = g["gross_exposure"].mean()
        s["avg_exante_vol"] = g["exante_vol"].mean()
        s["avg_n_positions"] = (g["n_long"] + g["n_short"]).mean()
        out[b] = s
    return pd.DataFrame(out).T


def hypotheses(rets: pd.DataFrame, ff: pd.DataFrame) -> pd.DataFrame:
    wide = rets.pivot(index="date", columns="book", values="excess_ret").sort_index()
    rows = []
    # H1: between-peer (industry-bet) books; filing claim = no positive premium
    between = wide[[f"B_{s}" for s in SCHEMES]]
    rw = romano_wolf(between)
    for b in between:
        s = metrics.summary(between[b], 12)
        rows.append({"hypothesis": "H1 between-peer premium > 0 (one-sided)", "book": b, "comparison": "cash",
                     "estimate_sharpe": s["sharpe"], "ci_lo": s["sharpe_ci95_lo"], "ci_hi": s["sharpe_ci95_hi"],
                     "stat": rw.loc[b, "t_stat"], "p_value": np.nan, "p_adjusted": rw.loc[b, "p_rw"],
                     "n_months": int(s["n_periods"])})
    # H2: finer / statistical peers vs FF49 (Holm across the two comparisons)
    h2 = []
    for s in ["SIC3", "RCLUST"]:
        t = sharpe_diff_hac(wide[f"C_{s}"], wide["C_FF49"])
        h2.append((f"C_{s}", t))
    ps = sorted([t["p_two_sided"] for _, t in h2])
    for b, t in h2:
        rank = ps.index(t["p_two_sided"])
        holm = min(1.0, max((len(ps) - i) * ps[i] for i in range(rank + 1)))
        rows.append({"hypothesis": "H2 Sharpe(peer scheme) - Sharpe(FF49) != 0", "book": b, "comparison": "C_FF49",
                     "estimate_sharpe": t["diff_ann"], "ci_lo": t["diff_ann"] - 1.96 * t["se_ann"],
                     "ci_hi": t["diff_ann"] + 1.96 * t["se_ann"], "stat": t["z"], "p_value": t["p_two_sided"],
                     "p_adjusted": holm, "n_months": t["n"]})
    # H3: explicit industry neutrality vs beta-only, same peer scheme
    for s in ["FF49"]:
        t = sharpe_diff_hac(wide[f"CN_{s}"], wide[f"C_{s}"])
        rows.append({"hypothesis": "H3 Sharpe(industry-neutral) - Sharpe(beta-only) != 0", "book": f"CN_{s}",
                     "comparison": f"C_{s}", "estimate_sharpe": t["diff_ann"], "ci_lo": t["diff_ann"] - 1.96 * t["se_ann"],
                     "ci_hi": t["diff_ann"] + 1.96 * t["se_ann"], "stat": t["z"], "p_value": t["p_two_sided"],
                     "p_adjusted": t["p_two_sided"], "n_months": t["n"]})
    # Secondary: is the peer-relative composite new relative to FF5 + UMD?
    fac = ff[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]]
    for b in ["C_ALL", "C_FF49", "CN_FF49"]:
        r = wide[b].copy()
        r.index = r.index + pd.offsets.MonthEnd(1)   # returns earned over the month after the signal date
        sp = spanning(r, fac)
        rows.append({"hypothesis": "S1 FF5+UMD spanning alpha", "book": b, "comparison": "FF5+UMD",
                     "estimate_sharpe": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "stat": sp["alpha_t"],
                     "p_value": np.nan, "p_adjusted": np.nan, "n_months": sp["n"],
                     "alpha_ann": sp["alpha_ann"], "r2": sp["r2"]})
    return pd.DataFrame(rows)


def figures(rets: pd.DataFrame, ics: pd.DataFrame, label: str, out: Path) -> None:
    wide = rets.pivot(index="date", columns="book", values="excess_ret").sort_index()
    fig, axes = plt.subplots(1, len(SCHEMES), figsize=(16, 3.6), sharey=True)
    for ax, s in zip(axes, SCHEMES):
        for b, style in [(f"W_{s}", "-"), (f"B_{s}", "--"), (f"C_{s}", ":")]:
            ax.plot(wide.index, (1 + wide[b]).cumprod() - 1, style, label=b)
        ax.axhline(0, color="grey", lw=0.6)
        if label == "full":   # shade evaluation periods
            for (a, b, c) in [("2017-01-01", "2019-12-31", "#f2e6d9"), ("2020-01-01", "2023-12-31", "#dde8f5"),
                              ("2024-01-01", "2026-12-31", "#e3f0e0")]:
                ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=c, zorder=0)
        ax.set_title(f"Peers: {s}")
        ax.legend(fontsize=7)
    axes[0].set_ylabel("cumulative net excess return")
    title = f"Within- vs between-peer components ({label}; net of costs, $100M NAV)"
    if label == "full":
        title += " — shaded: validation / TEST / recent"
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out / f"within_between_{label}.png", dpi=150)
    plt.close(fig)

    if not ics.empty:
        m = ics.mean()
        t = m / (ics.std() / np.sqrt(len(ics)))
        fig, ax = plt.subplots(figsize=(7, 3.2))
        ax.bar(m.index, m.values)
        for i, (v, tt) in enumerate(zip(m.values, t.values)):
            ax.text(i, v, f"t={tt:.1f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7)
        ax.axhline(0, color="grey", lw=0.6)
        ax.set_ylabel("mean monthly rank IC")
        ax.set_title(f"Theme information coefficients vs next-month return ({label}, n={len(ics)} months)")
        fig.tight_layout()
        fig.savefig(out / f"theme_ic_{label}.png", dpi=150)
        plt.close(fig)


def main(run_dirs: list[Path], label: str, start: str | None = None, end: str | None = None) -> None:
    rets, ics = load_runs(run_dirs)
    lo = pd.Timestamp(start) if start else pd.Timestamp.min
    hi = pd.Period(end).end_time if end else pd.Timestamp.max
    rets = rets[(rets["date"] >= lo) & (rets["date"] <= hi)]
    if not ics.empty:
        ics = ics[(ics.index >= lo) & (ics.index <= hi)]
    tables, figs = RESULTS / "tables", RESULTS / "figures"
    summ = book_summary(rets)
    summ.to_csv(tables / f"book_summary_{label}.csv")
    hyp = hypotheses(rets, factors())
    hyp.to_csv(tables / f"hypotheses_{label}.csv", index=False)
    if not ics.empty:
        pd.DataFrame({"mean_ic": ics.mean(), "t_stat": ics.mean() / (ics.std() / np.sqrt(len(ics))),
                      "n_months": len(ics)}).to_csv(tables / f"theme_ic_{label}.csv")
    figures(rets, ics, label, figs)
    cols = ["n_periods", "ann_return", "ann_vol", "sharpe", "sharpe_ci95_lo", "sharpe_ci95_hi", "max_drawdown",
            "gross_sharpe", "avg_turnover", "avg_cost_ann"]
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(summ[cols].sort_index())
        print(hyp.drop(columns=[c for c in ["alpha_ann", "r2"] if c not in hyp]).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--label", required=True)
    ap.add_argument("--start")
    ap.add_argument("--end")
    a = ap.parse_args()
    main([Path(r) for r in a.runs], a.label, a.start, a.end)
