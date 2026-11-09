"""D4: cross-check of the production cvxpy optimiser against skfolio MeanRisk on sampled months.
Same problem in both: maximise alpha'w - lam w'Sigma w - hs'|w - w0| s.t. beta'w = 0, ||w||_1 <= 2, |w_i| <= cap_i
(top-150 names by market cap; linear costs only, because skfolio cannot express the |dw|^1.5 impact term; Sigma is the
v1 PCA model, passed to skfolio as a pseudo-return matrix whose sample covariance equals Sigma).
Run: python scripts/v2/skfolio_check.py"""

import dataclasses
import json
import warnings

import cvxpy as cp
import numpy as np
import pandas as pd
from common import CFG, TAB, hash12, load_bt

from peerrel import risk
from peerrel.backtest import eligible
from peerrel.signals.scores import composite, theme_scores
from peerrel.v2.portfolio import optimise_v2

warnings.filterwarnings("ignore")
from skfolio.optimization import MeanRisk, ObjectiveFunction  # noqa: E402


def one_month(bt, panel, t, n=150):
    sig_day = bt.months.loc[t, "signal_day"]
    x = eligible(panel.loc[t], bt.cfg)
    th = theme_scores(x, None)
    x = x[th.notna().sum(axis=1) >= 3].nlargest(1000, "mcap")
    window = bt.daily_ret.loc[:sig_day].iloc[-252:].reindex(columns=x["ticker"])
    rm = risk.estimate(window, bt.ffd["Mkt-RF"], bt.ffd["RF"])
    x = x[x["ticker"].isin(rm.tickers)].nlargest(n, "mcap")
    pos = rm.tickers.get_indexer(pd.Index(x["ticker"]))
    s = composite(theme_scores(x, None)).fillna(0.0).to_numpy()
    d = rm.d[pos]
    alpha = bt.cfg.ic * np.sqrt(d * 21) * s
    hs = (x["spread"].fillna(x["spread"].median()).clip(lower=0.0002) / 2).to_numpy()
    adv = x["adv_63d"].to_numpy()
    cap = np.minimum(bt.opt.name_cap, bt.opt.adv_cap * adv / bt.opt.nav)
    L = rm.L[pos]
    Sig = (L @ L.T + np.diag(d)) * 21
    return alpha, rm.beta[pos], L, d, hs, adv, cap, Sig, x["vol_63d"].fillna(0.02).to_numpy()


def pseudo_returns(Sig):
    w, Q = np.linalg.eigh(Sig)
    X = np.sqrt(np.clip(w, 0, None))[:, None] * Q.T
    n = len(Sig)
    X = np.vstack([X, -X]) * np.sqrt((2 * n - 1) / 2)
    return pd.DataFrame(X)


def main():
    bt, panel = load_bt()
    rng = np.random.default_rng(0)
    w0_scale = 0.003
    out = {"prereg_hash": hash12(), "months": {}}
    opt = dataclasses.replace(bt.opt, impact_y=0.0)
    for t in [pd.Timestamp(m) for m in ("2015-06-30", "2018-06-29", "2022-06-30")]:
        t = panel.index.get_level_values("date").unique()[panel.index.get_level_values("date").unique().get_indexer([t], method="nearest")[0]]
        alpha, beta, L, d, hs, adv, cap, Sig, vol = one_month(bt, panel, t)
        n = len(alpha)
        w0 = rng.normal(0, w0_scale, n)
        w0 -= beta * (beta @ w0) / (beta @ beta)                        # start beta-neutral
        w_mine, info = optimise_v2(alpha, beta, L, d, w0, hs, vol, adv,
                                   dataclasses.replace(opt, name_cap=float(cap.max())), borrow_m=None)
        # per-name caps differ in v2 optimiser through ADV; pass the same caps to skfolio and recompute with them
        w_mine, info = optimise_v2(alpha, beta, L, d, w0, hs, vol, adv, opt, borrow_m=None)
        mr = MeanRisk(objective_function=ObjectiveFunction.MAXIMIZE_UTILITY, risk_aversion=opt.risk_aversion,
                      min_weights=-cap, max_weights=cap, budget=None, transaction_costs=hs, previous_weights=w0,
                      overwrite_expected_return=lambda w: alpha @ w,
                      add_constraints=lambda w: [beta @ w == 0, cp.norm1(w) <= opt.gross], raise_on_failure=False)
        mr.fit(pseudo_returns(Sig))
        w_sk = np.asarray(mr.weights_)

        def obj(w):
            return float(alpha @ w - opt.risk_aversion * w @ Sig @ w - hs @ np.abs(w - w0))
        out["months"][str(t.date())] = {
            "n": int(n), "weight_corr": float(np.corrcoef(w_mine, w_sk)[0, 1]),
            "objective_cvxpy": obj(w_mine), "objective_skfolio": obj(w_sk),
            "objective_gap_rel": float((obj(w_mine) - obj(w_sk)) / abs(obj(w_mine))),
            "gross_cvxpy": float(np.abs(w_mine).sum()), "gross_skfolio": float(np.abs(w_sk).sum()),
            "beta_skfolio": float(beta @ w_sk), "max_abs_weight_diff": float(np.abs(w_mine - w_sk).max())}
    (TAB / "skfolio_check.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
