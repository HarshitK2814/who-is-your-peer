"""H2: does the style (Barra-like) model forecast monthly risk better than v1's PCA-10 model?
Test portfolios are NOT optimised under either model: for each of the 15 characteristics, equal-weight top decile minus
bottom decile ($1 per leg) in the month's universe. Loss QLIKE = log(s2) + r^2/s2 (r = realised ret_fwd of the portfolio).
Statistic: month-mean over portfolios of QLIKE(PCA) - QLIKE(style), 2013-01..2019-12; bootstrap CI (block 6).
Signal bar t: both forecasts use days <= t only. Run: python scripts/v2/h2_riskmodel.py"""

import json

import numpy as np
import pandas as pd
from common import CFG, FIG, ROOT, RUNS, TAB, hash12, load_bt, signal_dates, slice_period

from peerrel import risk
from peerrel.backtest import eligible
from peerrel.signals.scores import CHARACTERISTICS, theme_scores
from peerrel.v2 import styledata
from peerrel.v2 import stylemodel as sm
from qcore.bootstrap import bootstrap_stat, percentile_ci

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def build_rows(bt, panel, table, hist, dates):
    expo = {d: g.set_index("ticker") for d, g in table.groupby("date")}
    rows = []
    for t in dates:
        sig_day = bt.months.loc[t, "signal_day"]
        x = eligible(panel.loc[t], bt.cfg)
        x = x[theme_scores(x, None).notna().sum(axis=1) >= 3].nlargest(bt.cfg.universe_size, "mcap")
        window = bt.daily_ret.loc[:sig_day].iloc[-252:].reindex(columns=x["ticker"])
        rm = risk.estimate(window, bt.ffd["Mkt-RF"], bt.ffd["RF"])
        x = x[x["ticker"].isin(rm.tickers)]
        order = pd.Index(x["ticker"])
        pos = rm.tickers.get_indexer(order)
        L, d = rm.L[pos], rm.d[pos]
        S = expo[t].reindex(order)[sm.STYLES].fillna(0.0)
        Xf = pd.concat([sm.industry_dummies(pd.Series(bt.static_groups["FF49"].reindex(x.index).to_numpy(), index=order).astype(float)), S], axis=1)[sm.FACTORS]
        try:
            m = sm.model_at(hist, sig_day, Xf)
        except ValueError:
            continue
        r = x["ret_fwd"].fillna(0.0).to_numpy()
        for c in CHARACTERISTICS:
            v = x[c].replace([np.inf, -np.inf], np.nan)
            ok = v.notna().to_numpy()
            if ok.sum() < 200:
                continue
            rk = v.rank(pct=True).to_numpy()
            top, bot = ok & (rk > 0.9), ok & (rk <= 0.1)
            w = np.zeros(len(x))
            w[top] = 1.0 / top.sum()
            w[bot] = -1.0 / bot.sum()
            s2_pca = 21 * (np.sum((L.T @ w) ** 2) + np.sum(d * w**2))
            s2_sty = 21 * (np.sum((m["L"].T @ w) ** 2) + np.sum(m["d"] * w**2))
            rows.append({"date": t, "char": c, "r": float(w @ r), "s2_pca": s2_pca, "s2_style": s2_sty})
        print(f"\r{t.date()}", end="", flush=True)
    print()
    return pd.DataFrame(rows)


def main():
    cache = RUNS / "h2_rows.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
    else:
        bt, panel = load_bt()
        table, hist = styledata.load_or_build(ROOT, panel, bt.daily_ret, bt.ffd["Mkt-RF"], bt.months.reset_index(),
                                              bt.static_groups["FF49"], bt.cfg)
        dates = signal_dates(panel, "2013-01-01")
        df = build_rows(bt, panel, table, hist, dates)
        df.to_parquet(cache)
    df["q_pca"] = np.log(df.s2_pca) + df.r**2 / df.s2_pca
    df["q_style"] = np.log(df.s2_style) + df.r**2 / df.s2_style
    df["z_pca"] = df.r / np.sqrt(df.s2_pca)
    df["z_style"] = df.r / np.sqrt(df.s2_style)
    out = {"prereg_hash": hash12(), "periods": {}}
    for plabel, (lo, hi) in {"design 2013-01..2019-12 (choice period)": ("2013-01-31", "2019-12-31"),
                             "2020-2026 seen period (v1 reported it)": ("2020-01-31", "2026-12-31")}.items():
        g = df[(df.date >= lo) & (df.date <= hi)]
        mm = g.groupby("date").apply(lambda a: (a.q_pca - a.q_style).mean(), include_groups=False)
        draws = bootstrap_stat(mm, lambda s: float(s.mean()), n_boot=5000, mean_block=6.0)
        ci = percentile_ci(draws)
        out["periods"][plabel] = {
            "n_months": int(mm.shape[0]), "n_portfolio_months": int(len(g)),
            "mean_qlike_diff_pca_minus_style": float(mm.mean()), "ci95": list(ci),
            "mean_qlike_pca": float(g.q_pca.mean()), "mean_qlike_style": float(g.q_style.mean()),
            "bias_std_pca": float(g.z_pca.std()), "bias_std_style": float(g.z_style.std()),
            "share_months_style_better": float((mm > 0).mean()),
            "mean_forecast_vol_ratio_style_over_pca": float(np.sqrt(g.s2_style / g.s2_pca).mean())}
    d = out["periods"]["design 2013-01..2019-12 (choice period)"]
    out["H2_supported"] = bool(d["mean_qlike_diff_pca_minus_style"] > 0 and d["ci95"][0] > 0)
    (TAB / "h2_riskmodel.json").write_text(json.dumps(out, indent=1))
    per = df[(df.date >= "2013-01-31") & (df.date <= "2019-12-31")].groupby("char")[["q_pca", "q_style"]].mean()
    per["diff"] = per.q_pca - per.q_style
    per.to_csv(TAB / "h2_by_characteristic.csv")
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.barh(per.index, per["diff"], color=np.where(per["diff"] > 0, "#4477aa", "#cc6677"))
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel("QLIKE(PCA) - QLIKE(style); positive = style model better")
    ax.set_title("Design period 2013-2019, decile-spread test portfolios")
    fig.tight_layout()
    fig.savefig(FIG / "h2_qlike_by_characteristic.png", dpi=130)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
