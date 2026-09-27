"""Post-hoc: which theme's industry component drives the industry-bet premium?
Plan and reading rules fixed beforehand in research/posthoc_theme_decomposition.md."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from industry_momentum_test import beta_hedged, book_returns  # noqa: E402

from qcore import metrics  # noqa: E402

from peerrel.config import RESULTS  # noqa: E402
from peerrel.data.french import factors  # noqa: E402

THEMES = ["quality", "management", "growth", "sentiment", "valuation"]
PERIODS = {"test_2020_2023": ("2020-02-29", "2024-01-31"), "full_2012_2026": ("2012-02-29", "2026-08-31"),
           "recent_2024_2026": ("2024-02-29", "2026-08-31")}
UNIVERSES = {"top1000": ("posthoc_themes", "full_main"), "top500": ("posthoc_themes_u500", "robust_univ500")}


def main() -> None:
    mkt = factors()["Mkt-RF"]
    rows, attrib = [], []
    for uname, (theme_tag, base_tag) in UNIVERSES.items():
        b = book_returns(base_tag, "B_FF49")
        books = {t: book_returns(theme_tag, f"BT_{t}.FF49") for t in THEMES}
        for t, y in books.items():
            h = beta_hedged(y, mkt)
            for pname, (lo, hi) in PERIODS.items():
                raw, hh = y.loc[lo:hi], h.loc[lo:hi]
                s = metrics.summary(hh, 12)
                rows.append({"universe": uname, "theme": t, "period": pname,
                             "sharpe_raw": metrics.sharpe(raw, 12), "sharpe_beta_hedged": s["sharpe"],
                             "hedged_ci_lo": s["sharpe_ci95_lo"], "hedged_ci_hi": s["sharpe_ci95_hi"],
                             "realised_beta": np.polyfit(mkt.reindex(raw.index), raw, 1)[0],
                             "corr_with_B_FF49": raw.corr(b.reindex(raw.index)), "n": len(hh)})
        X = pd.DataFrame(books)
        for pname in ["full_2012_2026", "test_2020_2023"]:
            lo, hi = PERIODS[pname]
            d = pd.concat([b.rename("B"), X], axis=1, join="inner").loc[lo:hi].dropna()
            f = sm.OLS(d["B"], sm.add_constant(d[THEMES])).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
            for t in THEMES:
                attrib.append({"universe": uname, "period": pname, "theme": t, "coef": f.params[t],
                               "t": f.tvalues[t], "r2": f.rsquared, "n": int(f.nobs)})
    tab, att = pd.DataFrame(rows), pd.DataFrame(attrib)
    tab.to_csv(RESULTS / "tables" / "posthoc_theme_between_books.csv", index=False)
    att.to_csv(RESULTS / "tables" / "posthoc_theme_attribution.csv", index=False)

    # reading rule
    verdict = []
    for uname in UNIVERSES:
        for t in THEMES:
            sh = tab.query("universe == @uname and theme == @t and period == 'test_2020_2023'")["sharpe_beta_hedged"].item()
            a = att.query("universe == @uname and theme == @t and period == 'full_2012_2026'").iloc[0]
            verdict.append({"universe": uname, "theme": t, "hedged_test_sharpe": sh, "attrib_coef_full": a["coef"],
                            "attrib_t_full": a["t"], "driver": bool(sh >= 0.5 and a["coef"] > 0 and a["t"] >= 2)})
    ver = pd.DataFrame(verdict)
    ver.to_csv(RESULTS / "tables" / "posthoc_theme_verdict.csv", index=False)

    # figure: beta-hedged Sharpe by theme, test vs full, both universes
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), sharey=True)
    for ax, uname in zip(axes, UNIVERSES):
        sub = tab[tab["universe"] == uname].pivot(index="theme", columns="period", values="sharpe_beta_hedged").loc[THEMES]
        sub[["full_2012_2026", "test_2020_2023", "recent_2024_2026"]].plot.bar(ax=ax, rot=0)
        ax.axhline(0, color="grey", lw=0.6)
        ax.set_title(f"{uname}: industry component per theme\n(beta-hedged net Sharpe)")
    axes[0].set_ylabel("annualised Sharpe")
    fig.tight_layout()
    fig.savefig(RESULTS / "figures" / "posthoc_theme_decomposition.png", dpi=150)

    with pd.option_context("display.width", 220, "display.float_format", "{:.2f}".format):
        print(tab.to_string(index=False))
        print(att.to_string(index=False))
        print(ver.to_string(index=False))


def return_contributions() -> pd.DataFrame:
    """Each theme's contribution to B_FF49's mean return = attribution coefficient x theme-book mean return.
    (The attribution regression is near-mechanical, R^2 ~0.9, so coefficients alone say little about *returns*.)"""
    from industry_momentum_test import indmom, industry_returns
    att = pd.read_csv(RESULTS / "tables" / "posthoc_theme_attribution.csv")
    m6, _ = indmom(industry_returns(), 6, 0)
    rows = []
    for u, (tt, bt) in UNIVERSES.items():
        for p in ["test_2020_2023", "full_2012_2026"]:
            lo, hi = PERIODS[p]
            for t in THEMES:
                y = book_returns(tt, f"BT_{t}.FF49").loc[lo:hi]
                c = att.query("universe == @u and period == @p and theme == @t")["coef"].item()
                rows.append({"universe": u, "period": p, "theme": t, "return_contrib_pct_yr": 100 * c * y.mean() * 12,
                             "corr_INDMOM_6_0": y.corr(m6.reindex(y.index))})
            b = book_returns(bt, "B_FF49").loc[lo:hi]
            rows.append({"universe": u, "period": p, "theme": "= B_FF49 total", "return_contrib_pct_yr": 100 * b.mean() * 12,
                         "corr_INDMOM_6_0": b.corr(m6.reindex(b.index))})
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "tables" / "posthoc_theme_return_contributions.csv", index=False)
    return out


if __name__ == "__main__":
    main()
    print(return_contributions().to_string(index=False))
