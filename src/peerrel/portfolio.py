"""Beta-neutral long/short optimiser (cvxpy).

    max  alpha'w - lam * w' Sigma w - sum_i [ hs_i |dw_i| + Y sigma_i sqrt(NAV/ADV_i) |dw_i|^1.5 ]
    s.t. beta'w = 0, ||w||_1 <= gross, |w_i| <= cap_i, [H'w = 0]

Sigma is in monthly units (daily factor model x 21). The |dw|^1.5 term is the
square-root-law market impact integrated over the trade (cost per $ ~ sqrt(size)).
"""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np


@dataclass
class OptConfig:
    risk_aversion: float
    gross: float = 2.0
    name_cap: float = 0.01
    adv_cap: float = 0.05          # max position as a fraction of 63d median dollar volume
    nav: float = 100e6
    impact_y: float = 0.5
    solver: str = "CLARABEL"


def optimise(alpha: np.ndarray, beta: np.ndarray, L: np.ndarray, d: np.ndarray, w0: np.ndarray,
             half_spread: np.ndarray, daily_vol: np.ndarray, adv: np.ndarray, cfg: OptConfig,
             H: np.ndarray | None = None) -> np.ndarray:
    n = len(alpha)
    w = cp.Variable(n)
    dw = w - w0
    L_m, d_m = L * np.sqrt(21), d * 21
    risk = cp.sum_squares(L_m.T @ w) + cp.sum(cp.multiply(d_m, cp.square(w)))
    impact_coef = cfg.impact_y * daily_vol * np.sqrt(cfg.nav / np.maximum(adv, 1.0))
    cost = half_spread @ cp.abs(dw) + impact_coef @ cp.power(cp.abs(dw), 1.5)
    cap = np.minimum(cfg.name_cap, cfg.adv_cap * adv / cfg.nav)
    cons = [beta @ w == 0, cp.norm1(w) <= cfg.gross, cp.abs(w) <= cap]
    if H is not None and H.shape[1] > 0:
        cons.append(H.T @ w == 0)
    prob = cp.Problem(cp.Maximize(alpha @ w - cfg.risk_aversion * risk - cost), cons)
    try:
        prob.solve(solver=cfg.solver)
    except cp.SolverError:
        prob.solve(solver="ECOS")
    if w.value is None or prob.status not in ("optimal", "optimal_inaccurate"):
        return np.zeros(n)
    x = np.asarray(w.value).ravel()
    x[np.abs(x) < 1e-7] = 0.0
    return x


def trade_cost(dw: np.ndarray, half_spread: np.ndarray, daily_vol: np.ndarray, adv: np.ndarray,
               cfg: OptConfig) -> float:
    """Realised cost of a trade as a fraction of NAV (same model as in the objective)."""
    impact_coef = cfg.impact_y * daily_vol * np.sqrt(cfg.nav / np.maximum(adv, 1.0))
    return float(half_spread @ np.abs(dw) + impact_coef @ np.abs(dw) ** 1.5)
