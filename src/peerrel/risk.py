"""Monthly risk inputs estimated from the trailing 252 trading days ending at the signal bar.

* beta: OLS slope on the Fama-French market excess return, shrunk 2/3 to the estimate and
  1/3 to 1 (Vasicek-style; reduces noise in the beta-neutrality constraint)
* statistical factor model: PCA on excess returns (k factors) + diagonal idiosyncratic variance
      Sigma = L L' + diag(d),   L = loadings * sqrt(factor variances)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class RiskModel:
    tickers: pd.Index
    beta: np.ndarray          # (n,)
    L: np.ndarray             # (n, k) factor exposure * sqrt(factor variance), daily units
    d: np.ndarray             # (n,) idiosyncratic daily variance
    resid: pd.DataFrame       # (T, n) market-model residual returns (for return-based peers)

    def annual_vol(self, w: np.ndarray) -> float:
        var = np.sum((self.L.T @ w) ** 2) + np.sum(self.d * w**2)
        return float(np.sqrt(var * 252))


def estimate(returns: pd.DataFrame, mkt_excess: pd.Series, rf: pd.Series, k: int = 10,
             min_obs: int = 200) -> RiskModel:
    """returns: (T, n) daily simple returns over the trailing window (NaN allowed)."""
    rf = rf.reindex(returns.index).fillna(0.0)
    mkt = mkt_excess.reindex(returns.index).fillna(0.0).to_numpy()
    ex = returns.sub(rf, axis=0)
    valid = ex.notna()
    keep = valid.sum() >= min_obs
    ex, valid = ex.loc[:, keep], valid.loc[:, keep]
    X = ex.fillna(0.0).to_numpy()
    M = valid.to_numpy()

    # per-stock beta on its own valid days
    mk = mkt[:, None] * M
    mk_mean = mk.sum(0) / M.sum(0)
    x_mean = X.sum(0) / M.sum(0)
    cov = ((mk - mk_mean) * (X - x_mean) * M).sum(0)
    var = (((mk - mk_mean) ** 2) * M).sum(0)
    beta_raw = cov / var
    beta = 2 / 3 * beta_raw + 1 / 3

    resid = (X - x_mean - beta_raw * (mk - mk_mean)) * M
    # PCA on standardised excess returns -> loadings in return units
    Xc = (X - x_mean) * M
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    T = M.shape[0]
    f_var = S[:k] ** 2 / (T - 1)
    L = Vt[:k].T * np.sqrt(f_var)
    common = Xc @ Vt[:k].T @ Vt[:k]
    d = ((Xc - common) ** 2).sum(0) / np.maximum(M.sum(0) - 1, 1)
    d = np.maximum(d, np.quantile(d, 0.05))   # floor tiny idiosyncratic variances
    return RiskModel(ex.columns, beta, L, d, pd.DataFrame(resid, index=ex.index, columns=ex.columns))
