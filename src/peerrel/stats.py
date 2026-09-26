"""Inference for the pre-registered hypotheses.

* sharpe_diff_hac  - HAC (Newey-West) delta-method test of a Sharpe-ratio difference between two
                     strategies on the same dates, as in Ledoit & Wolf (2008) (without their
                     prewhitening step);
* romano_wolf      - stepdown multiple-testing adjustment for H0: E[r_j] <= 0 across strategies,
                     with the stationary bootstrap (Romano & Wolf 2005);
* spanning         - OLS alpha on FF5 + UMD with Newey-West standard errors;
* deflated_sharpe  - probability the observed Sharpe beats the expected maximum of N trials
                     under the null (Bailey & Lopez de Prado 2014).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from qcore.bootstrap import stationary_indices


def _nw_cov(u: np.ndarray, lags: int) -> np.ndarray:
    u = u - u.mean(0)
    n = len(u)
    s = u.T @ u / n
    for k in range(1, lags + 1):
        g = u[k:].T @ u[:-k] / n
        s += (1 - k / (lags + 1)) * (g + g.T)
    return s


def sharpe_diff_hac(r1: pd.Series, r2: pd.Series, periods: int = 12, lags: int = 6) -> dict:
    df = pd.concat([r1, r2], axis=1).dropna()
    x = df.to_numpy()
    n = len(x)
    mu, m2 = x.mean(0), (x**2).mean(0)
    sig = np.sqrt(m2 - mu**2)
    diff = mu[0] / sig[0] - mu[1] / sig[1]
    # gradient of f(mu1, mu2, m2_1, m2_2) = mu1/sqrt(m2_1-mu1^2) - mu2/sqrt(m2_2-mu2^2)
    grad = np.array([m2[0] / sig[0] ** 3, -m2[1] / sig[1] ** 3, -mu[0] / (2 * sig[0] ** 3), mu[1] / (2 * sig[1] ** 3)])
    u = np.column_stack([x[:, 0], x[:, 1], x[:, 0] ** 2, x[:, 1] ** 2])
    se = np.sqrt(grad @ _nw_cov(u, lags) @ grad / n)
    z = diff / se
    return {"sharpe_1": mu[0] / sig[0] * np.sqrt(periods), "sharpe_2": mu[1] / sig[1] * np.sqrt(periods),
            "diff_ann": diff * np.sqrt(periods), "se_ann": se * np.sqrt(periods),
            "z": z, "p_two_sided": 2 * stats.norm.sf(abs(z)), "n": n}


def romano_wolf(returns: pd.DataFrame, n_boot: int = 5000, mean_block: float = 6.0, seed: int = 0) -> pd.DataFrame:
    """Stepdown p-values for one-sided H0_j: mean_j <= 0, studentised by the sample std."""
    x = returns.dropna().to_numpy()
    n, k = x.shape
    mean, sd = x.mean(0), x.std(0, ddof=1)
    t_obs = mean / (sd / np.sqrt(n))
    rng = np.random.default_rng(seed)
    boot = np.empty((n_boot, k))
    for b in range(n_boot):
        xb = x[stationary_indices(n, mean_block, rng)]
        boot[b] = (xb.mean(0) - mean) / (xb.std(0, ddof=1) / np.sqrt(n))
    order = np.argsort(-t_obs)
    p_adj = np.empty(k)
    running = 0.0
    for step, j in enumerate(order):
        remaining = order[step:]
        max_t = boot[:, remaining].max(axis=1)
        p = float((max_t >= t_obs[j]).mean())
        running = max(running, p)
        p_adj[j] = running
    return pd.DataFrame({"t_stat": t_obs, "p_rw": p_adj}, index=returns.columns)


def spanning(r: pd.Series, factors: pd.DataFrame, lags: int = 6) -> pd.Series:
    df = pd.concat([r.rename("r"), factors], axis=1, join="inner").dropna()
    X = sm.add_constant(df[factors.columns])
    fit = sm.OLS(df["r"], X).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    out = fit.params.add_prefix("b_")
    out["alpha_ann"] = fit.params["const"] * 12
    out["alpha_t"] = fit.tvalues["const"]
    out["r2"] = fit.rsquared
    out["n"] = int(fit.nobs)
    return out


def deflated_sharpe(r: pd.Series, n_trials: int, sr_trials_std: float | None = None) -> float:
    """PSR of the (per-period) Sharpe against the expected max Sharpe of `n_trials` null trials."""
    r = r.dropna()
    n = len(r)
    sr = r.mean() / r.std(ddof=1)
    skew, kurt = stats.skew(r), stats.kurtosis(r, fisher=False)
    v = sr_trials_std**2 if sr_trials_std is not None else 1.0 / n
    emc = 0.5772156649
    sr0 = np.sqrt(v) * ((1 - emc) * stats.norm.ppf(1 - 1 / n_trials) + emc * stats.norm.ppf(1 - 1 / (n_trials * np.e)))
    z = (sr - sr0) * np.sqrt(n - 1) / np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2)
    return float(stats.norm.cdf(z))
