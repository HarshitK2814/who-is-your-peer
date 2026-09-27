"""Post-hoc: is the between-industry (industry-bet) premium just industry momentum?
Plan and decision rule fixed beforehand in research/posthoc_industry_momentum.md."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from peerrel.config import INTERIM, RESULTS  # noqa: E402
from peerrel.data.french import _read_first_table, assign_industry, factors  # noqa: E402

# Returns are indexed by the month they are EARNED (signal month + 1), so the pre-registered test period
# (signals 2020-01 .. 2023-12) corresponds to earned months 2020-02 .. 2024-01.
PERIODS = {"test_2020_2023": ("2020-02-29", "2024-01-31"), "full_2012_2026": ("2012-02-29", "2026-08-31")}


def industry_returns() -> pd.DataFrame:
    r = _read_first_table("49_Industry_Portfolios_CSV.zip", 6)
    return r.where(r > -0.99)   # -99.99 = missing in the French files


def indmom(ind: pd.DataFrame, lookback: int, skip: int, n: int = 15) -> tuple[pd.Series, pd.DataFrame]:
    """Returns (factor return indexed by the month it is EARNED, formation scores indexed by formation month-end)."""
    logr = np.log1p(ind)
    score = logr.rolling(lookback, min_periods=lookback).sum().shift(skip)
    rank = score.rank(axis=1, ascending=False)
    k = score.notna().sum(axis=1)
    long = rank.le(n)
    short = rank.gt(k.to_numpy()[:, None] - n) & score.notna()
    w = long.astype(float).div(long.sum(axis=1), axis=0) - short.astype(float).div(short.sum(axis=1), axis=0)
    fac = (w.shift(1) * ind).sum(axis=1, min_count=1)   # weights formed at t-1, return in month t
    return fac.rename(f"INDMOM_{lookback}_{skip}"), score


def spanning(y: pd.Series, X: pd.DataFrame) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1, join="inner").dropna()
    f = sm.OLS(d["y"], sm.add_constant(d[X.columns])).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    out = {"alpha_ann": f.params["const"] * 12, "alpha_t": f.tvalues["const"], "r2": f.rsquared, "n": int(f.nobs)}
    for c in X.columns:
        out[f"b_{c}"], out[f"t_{c}"] = f.params[c], f.tvalues[c]
    return out


def book_returns(tag: str, book: str = "B_FF49") -> pd.Series:
    d = sorted((RESULTS / "runs").glob(f"*_{tag}"))[-1]
    r = pd.read_parquet(d / "returns.parquet")
    s = r[r["book"] == book].set_index("date")["excess_ret"].sort_index()
    s.index = s.index + pd.offsets.MonthEnd(1)   # earned over the month after the signal date
    return s


def exposure_overlap(tag: str, score: pd.DataFrame) -> pd.Series:
    """Monthly Spearman correlation between B_FF49's net weight per FF49 industry and the industries'
    past-return score known at the signal date."""
    d = sorted((RESULTS / "runs").glob(f"*_{tag}"))[-1]
    w = pd.read_parquet(d / "weights.parquet")
    w = w[w["book"] == "B_FF49"]
    comp = pd.read_parquet(INTERIM / "companies.parquet")
    ind_id = assign_industry(comp.set_index("ticker")["sic"].astype(float), 49)
    names = list(score.columns)
    w["ind"] = w["ticker"].map(ind_id).map(lambda i: names[int(i) - 1] if pd.notna(i) else None)
    net = w.dropna(subset=["ind"]).groupby(["date", "ind"])["w"].sum().unstack().fillna(0.0)
    out = {}
    for t in net.index:
        if t in score.index:
            s = score.loc[t].dropna()
            common = s.index.intersection(net.columns)
            out[t] = net.loc[t, common].corr(s[common], method="spearman")
    return pd.Series(out)


def main() -> None:
    ind = industry_returns()
    ff = factors()
    m6, score6 = indmom(ind, 6, 0)
    m12, _ = indmom(ind, 12, 1)
    base = ff[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]]
    rows = []
    for tag, label in [("full_main", "main"), ("robust_nomom", "composite without stock momentum")]:
        y = book_returns(tag)
        for pname, (lo, hi) in PERIODS.items():
            yy = y.loc[lo:hi]
            for spec, X in [("FF5+UMD", base), ("FF5+UMD+INDMOM_6_0", base.join(m6)),
                            ("FF5+UMD+INDMOM_12_1", base.join(m12)), ("INDMOM_6_0 only", m6.to_frame())]:
                rows.append({"run": label, "period": pname, "model": spec, **spanning(yy, X)})
    tab = pd.DataFrame(rows)
    tab.to_csv(RESULTS / "tables" / "posthoc_industry_momentum_spanning.csv", index=False)

    # decision rule (primary: main run, INDMOM_6_0)
    verdicts = []
    for (run, pname), g in tab.groupby(["run", "period"]):
        a0 = g.loc[g["model"] == "FF5+UMD", "alpha_ann"].item()
        g1 = g[g["model"] == "FF5+UMD+INDMOM_6_0"].iloc[0]
        drop = 1 - g1["alpha_ann"] / a0 if a0 > 0 else np.nan
        t_ind = g1["t_INDMOM_6_0"]
        if drop > 0.5 and abs(t_ind) >= 2:
            v = "mostly industry momentum"
        elif (drop < 0.25) or abs(t_ind) < 2:
            v = "not industry momentum"
        else:
            v = "partly industry momentum"
        verdicts.append({"run": run, "period": pname, "alpha_FF5UMD": a0, "alpha_with_INDMOM": g1["alpha_ann"],
                         "alpha_drop": drop, "t_INDMOM_6_0": t_ind, "b_INDMOM_6_0": g1["b_INDMOM_6_0"], "verdict": v})
    ver = pd.DataFrame(verdicts)
    ver.to_csv(RESULTS / "tables" / "posthoc_industry_momentum_verdict.csv", index=False)

    ov = exposure_overlap("full_main", score6)
    ov_stats = {}
    for pname, (lo, hi) in PERIODS.items():
        x = ov.loc[lo:hi].dropna()
        ov_stats[pname] = {"mean_rank_corr": x.mean(), "t": x.mean() / x.std() * np.sqrt(len(x)), "n": len(x)}
    pd.DataFrame(ov_stats).T.to_csv(RESULTS / "tables" / "posthoc_industry_momentum_overlap.csv")

    # figure: cumulative B_FF49 vs industry momentum, full sample
    y = book_returns("full_main")
    d = pd.concat([y.rename("B_FF49 (industry-bet book, net)"), m6.rename("Industry momentum 6-0 (gross, no costs)")],
                  axis=1).loc["2012-02":].dropna()
    fig, ax = plt.subplots(1, 2, figsize=(13, 4))
    (1 + d).cumprod().sub(1).plot(ax=ax[0])
    ax[0].axvspan(pd.Timestamp("2020-02-01"), pd.Timestamp("2024-01-31"), color="#dde8f5", zorder=0)
    ax[0].set_title("Cumulative return (shaded: pre-registered test period)")
    ax[0].axhline(0, color="grey", lw=0.6)
    ov.rolling(12).mean().plot(ax=ax[1])
    ax[1].axhline(0, color="grey", lw=0.6)
    ax[1].set_title("Rank corr: B_FF49 industry weights vs\npast 6m industry return (12m avg)")
    fig.tight_layout()
    fig.savefig(RESULTS / "figures" / "posthoc_industry_momentum.png", dpi=150)

    with pd.option_context("display.width", 250, "display.float_format", "{:.3f}".format):
        cols = ["run", "period", "model", "alpha_ann", "alpha_t", "r2", "n"] + [c for c in tab.columns if c.startswith("t_IND") or c.startswith("b_IND") or c == "b_UMD"]
        print(tab[cols].to_string(index=False))
        print(ver.to_string(index=False))
        print(pd.DataFrame(ov_stats).T)
        print("corr(B_FF49, INDMOM_6_0) full:", round(d.corr().iloc[0, 1], 3))


def beta_hedged(y: pd.Series, mkt: pd.Series, window: int = 36, min_obs: int = 24) -> pd.Series:
    """Hedge a book's realised market beta using ONLY past months: beta_t is estimated from the book's
    returns over months t-window..t-1 (no look-ahead), then r_hedged_t = r_t - beta_t * MKT_t."""
    d = pd.concat([y.rename("y"), mkt.rename("m")], axis=1, join="inner").dropna()
    cov = d["y"].rolling(window, min_periods=min_obs).cov(d["m"]).shift(1)
    var = d["m"].rolling(window, min_periods=min_obs).var().shift(1)
    return (d["y"] - cov / var * d["m"]).dropna()


def hedged_report() -> pd.DataFrame:
    from qcore import metrics
    ff = factors()
    rows = []
    for tag in ["full_main", "robust_univ500"]:
        for book in ["B_FF49", "C_FF49", "CN_FF49", "W_FF49"]:
            y = book_returns(tag, book)
            h = beta_hedged(y, ff["Mkt-RF"])
            for pname, (lo, hi) in {**PERIODS, "recent_2024_2026": ("2024-02-29", "2026-08-31")}.items():
                raw, hh = y.loc[lo:hi], h.loc[lo:hi]
                s_raw, s_h = metrics.summary(raw, 12), metrics.summary(hh, 12)
                rows.append({"run": tag, "book": book, "period": pname, "sharpe_raw": s_raw["sharpe"],
                             "sharpe_beta_hedged": s_h["sharpe"], "ci_lo": s_h["sharpe_ci95_lo"],
                             "ci_hi": s_h["sharpe_ci95_hi"], "realised_beta": np.polyfit(
                                 ff["Mkt-RF"].reindex(raw.index), raw, 1)[0], "n": len(hh)})
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "tables" / "posthoc_beta_hedged.csv", index=False)
    return out


if __name__ == "__main__":
    main()
    with pd.option_context("display.width", 200, "display.float_format", "{:.2f}".format):
        print(hedged_report().to_string(index=False))
