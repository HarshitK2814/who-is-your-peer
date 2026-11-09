"""E1 (EXPLORATORY, never headline): what drives the peer-relative signal? Gradient-boosted model of the 15
within-FF49 rank-gaussian characteristics -> cross-sectional rank of next-month return (ret_fwd).
Train 2012-01..2016-10 (two-month gap before evaluation because ret_fwd of month s ends after month s+1 starts),
evaluate 2017-01..2019-12 (design period). Compare rank IC with the equal-weight composite; SHAP by characteristic and theme.
Signal bar: features at month-end t (data <= t); target = ret_fwd (t+1 close to next month t+1 close).
Run: python scripts/v2/shap_signal.py"""

import json

import numpy as np
import pandas as pd
import shap
from common import FIG, TAB, hash12, load_bt, signal_dates
from scipy.stats import norm, spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor

from peerrel.backtest import eligible
from peerrel.signals.peers import resolve_small_groups
from peerrel.signals.scores import CHARACTERISTICS, THEMES, composite, rank_gaussian, theme_scores, winsorize
from qcore.bootstrap import bootstrap_stat, percentile_ci

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

THEME_OF = {c: t for t, cs in THEMES.items() for c in cs}


def month_frame(bt, panel, t):
    x = eligible(panel.loc[t], bt.cfg)
    x = x[theme_scores(x, None).notna().sum(axis=1) >= 3].nlargest(bt.cfg.universe_size, "mcap")
    g = bt.static_groups.reindex(x.index).copy()
    lab = resolve_small_groups(g, "FF49")
    F = pd.DataFrame({c: rank_gaussian(winsorize(x[c]), lab) for c in CHARACTERISTICS if c in x})
    comp = composite(theme_scores(x, lab))
    y = x["ret_fwd"]
    y = pd.Series(norm.ppf((y.rank() - 0.5) / y.notna().sum()), index=x.index).where(y.notna())
    F["date"], F["y"], F["composite"], F["ret"] = t, y, comp, x["ret_fwd"]
    return F


def main():
    bt, panel = load_bt()
    dates = signal_dates(panel, "2012-01-01", "2019-12-31")
    df = pd.concat([month_frame(bt, panel, t) for t in dates])
    feats = [c for c in CHARACTERISTICS if c in df]
    tr = df[(df.date <= "2016-10-31") & df.y.notna()]
    te = df[(df.date >= "2017-01-31") & df.y.notna()]
    mdl = HistGradientBoostingRegressor(max_depth=3, max_iter=200, learning_rate=0.05, l2_regularization=1.0,
                                        min_samples_leaf=200, random_state=0).fit(tr[feats], tr["y"])
    te = te.assign(pred=mdl.predict(te[feats]))
    ic = te.groupby("date").apply(lambda g: pd.Series({
        "gbm": spearmanr(g.pred, g.ret, nan_policy="omit")[0],
        "composite": spearmanr(g.composite, g.ret, nan_policy="omit")[0]}), include_groups=False)
    diff = ic["gbm"] - ic["composite"]
    draws = bootstrap_stat(diff, lambda s: float(s.mean()), n_boot=5000, mean_block=6.0)
    ci = percentile_ci(draws)
    sub = te.sample(min(len(te), 20000), random_state=0)
    sv = shap.TreeExplainer(mdl).shap_values(sub[feats])
    imp = pd.Series(np.abs(sv).mean(0), index=feats).sort_values(ascending=False)
    by_theme = imp.groupby(imp.index.map(THEME_OF)).sum().sort_values(ascending=False)
    out = {"prereg_hash": hash12(), "label": "EXPLORATORY", "train_months": int(tr.date.nunique()),
           "eval_months": int(ic.shape[0]), "eval_rows": int(len(te)),
           "mean_ic_gbm": float(ic.gbm.mean()), "mean_ic_composite": float(ic.composite.mean()),
           "ic_diff_gbm_minus_composite": float(diff.mean()), "ic_diff_ci95": list(ci),
           "ic_diff_ci_excludes_zero": bool(ci[0] > 0 or ci[1] < 0),
           "shap_by_theme": by_theme.to_dict()}
    imp.rename("mean_abs_shap").to_csv(TAB / "shap_by_characteristic.csv")
    (TAB / "shap_signal.json").write_text(json.dumps(out, indent=1))
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    imp[::-1].plot.barh(ax=ax, color="#4477aa")
    ax.set_xlabel("mean |SHAP| (rank-return units), evaluation 2017-2019")
    ax.set_title("EXPLORATORY: what the boosted model uses")
    fig.tight_layout()
    fig.savefig(FIG / "shap_by_characteristic.png", dpi=130)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
