"""v2 optimiser: v1 problem plus (optional) style-neutral rows, a one-way turnover cap and a tiered borrow cost.

    max  alpha'w - lam w'Sigma w - cost(dw) - sum_i b_i max(-w_i, 0)       [b_i = monthly borrow rate]
    s.t. beta'w = 0, ||w||_1 <= gross, |w_i| <= cap_i, [H'w = 0], [|S'w| <= tol], [||w - w0||_1 / 2 <= turnover_cap]

With every option off and b = 0 this is exactly the v1 problem (parity test).
"""

from __future__ import annotations

import cvxpy as cp
import numpy as np

from peerrel.portfolio import OptConfig


def tier_borrow_bps(mcap: np.ndarray, bps: list[float], cuts: list[int]) -> np.ndarray:
    """Annual borrow fee per stock from its market-cap rank (1 = largest) in the universe."""
    rank = (-np.asarray(mcap)).argsort().argsort() + 1
    out = np.full(len(rank), float(bps[-1]))
    for k in range(len(cuts) - 1, -1, -1):
        out[rank <= cuts[k]] = float(bps[k])
    return out


def optimise_v2(alpha, beta, L, d, w0, half_spread, daily_vol, adv, cfg: OptConfig, H=None, S=None,
                style_tol: float = 0.05, turnover_cap: float | None = None, borrow_m: np.ndarray | None = None):
    """Returns (w, info). info: status, fallback (True if the turnover cap was infeasible and dropped)."""
    n = len(alpha)
    L_m, d_m = L * np.sqrt(21), d * 21
    impact_coef = cfg.impact_y * daily_vol * np.sqrt(cfg.nav / np.maximum(adv, 1.0))
    cap = np.minimum(cfg.name_cap, cfg.adv_cap * adv / cfg.nav)

    def solve(use_cap: bool):
        w = cp.Variable(n)
        dw = w - w0
        risk = cp.sum_squares(L_m.T @ w) + cp.sum(cp.multiply(d_m, cp.square(w)))
        cost = half_spread @ cp.abs(dw) + impact_coef @ cp.power(cp.abs(dw), 1.5)
        if borrow_m is not None:
            cost = cost + borrow_m @ cp.neg(w)
        cons = [beta @ w == 0, cp.norm1(w) <= cfg.gross, cp.abs(w) <= cap]
        if H is not None and H.shape[1] > 0:
            cons.append(H.T @ w == 0)
        if S is not None:
            cons.append(cp.abs(S.T @ w) <= style_tol)
        if use_cap and turnover_cap is not None:
            cons.append(cp.norm1(dw) / 2 <= turnover_cap)
        obj = alpha @ w - cfg.risk_aversion * risk - cost
        # retry ladder: Clarabel can fail numerically on these badly scaled problems (v1 silently returned a flat book
        # in 2 months; see experiment_log_v2.md). 1: default; 2: objective x1e3; 3: looser tolerances.
        prob = cp.Problem(cp.Maximize(obj), cons)
        for scale, opts in ((1.0, {}), (1e3, {}), (1.0, dict(tol_gap_abs=1e-6, tol_gap_rel=1e-6, tol_feas=1e-6, max_iter=400))):
            prob = cp.Problem(cp.Maximize(scale * obj), cons)
            try:
                prob.solve(solver=cfg.solver, **opts)
            except cp.SolverError:
                continue
            if w.value is not None and prob.status in ("optimal", "optimal_inaccurate"):
                break
        return w, prob

    capped = turnover_cap is not None and bool(np.any(w0 != 0))
    w, prob = solve(capped)
    fallback = False
    if (w.value is None or prob.status not in ("optimal", "optimal_inaccurate")) and capped:
        w, prob = solve(False)
        fallback = True
    if w.value is None or prob.status not in ("optimal", "optimal_inaccurate"):
        return np.zeros(n), {"status": str(prob.status), "fallback": fallback, "failed": True}
    x = np.asarray(w.value).ravel()
    x[np.abs(x) < 1e-7] = 0.0
    return x, {"status": str(prob.status), "fallback": fallback, "failed": False}
