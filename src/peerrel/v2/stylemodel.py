"""Small Barra-like fundamental risk model from free data (v2).

Factors: FF49 industry dummies + 8 styles. Daily factor returns come from WLS cross-sections of daily
returns on the exposures of the latest month-end STRICTLY BEFORE each day (so a day's exposures never use
that day or later). A forecast made at signal bar t uses only days <= t. See research/preregistration_v2.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

STYLES = ["size", "value", "momentum", "profitability", "leverage", "investment", "volatility", "beta"]
IND = [f"ind{i}" for i in range(1, 50)]
FACTORS = IND + STYLES


def _z(s: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    s = s.replace([np.inf, -np.inf], np.nan)
    if s.notna().sum() < 3:
        return pd.Series(0.0, index=s.index)
    s = s.clip(*s.quantile([lo, hi]))
    sd = s.std(ddof=0)
    if not np.isfinite(sd) or sd < 1e-12:
        return pd.Series(0.0, index=s.index)
    return ((s - s.mean()) / sd).fillna(0.0)


def market_beta(window: pd.DataFrame, mkt: pd.Series, min_obs: int = 126) -> pd.Series:
    """OLS slope of each column on the market over the window (NaN-aware); NaN if too few obs."""
    m = mkt.reindex(window.index).fillna(0.0).to_numpy()[:, None]
    X = window.to_numpy(dtype=float)
    ok = np.isfinite(X)
    n = ok.sum(0)
    Xz = np.where(ok, X, 0.0)
    mk = m * ok
    nn = np.maximum(n, 1)
    mk_mean = mk.sum(0) / nn
    x_mean = Xz.sum(0) / nn
    cov = ((mk - mk_mean * ok) * (Xz - x_mean * ok)).sum(0)
    var = ((mk - mk_mean * ok) ** 2).sum(0)
    b = np.where((n >= min_obs) & (var > 0), cov / np.where(var > 0, var, 1), np.nan)
    return pd.Series(b, index=window.columns)


def style_exposures(x: pd.DataFrame, beta: pd.Series) -> pd.DataFrame:
    """x: one month's universe (columns mcap, book_to_market, mom_12_1, gp_to_assets, leverage_neg,
    asset_growth_neg, vol_63d). beta: Series indexed like x. Standardised within the universe, missing -> 0."""
    out = pd.DataFrame(index=x.index)
    out["size"] = _z(np.log(x["mcap"]))
    out["value"] = _z(x["book_to_market"])
    out["momentum"] = _z(x["mom_12_1"])
    out["profitability"] = _z(x["gp_to_assets"])
    out["leverage"] = _z(-x["leverage_neg"])
    out["investment"] = _z(x["asset_growth_neg"])
    out["volatility"] = _z(x["vol_63d"])
    out["beta"] = _z(beta.reindex(x.index))
    return out[STYLES]


def industry_dummies(ind: pd.Series) -> pd.DataFrame:
    """ind: FF49 id per row (NaN allowed). Returns n x 49 float dummies (unmapped rows are all zero)."""
    d = pd.DataFrame(0.0, index=ind.index, columns=IND)
    for i in range(1, 50):
        d[f"ind{i}"] = (ind == i).astype(float)
    return d


@dataclass
class StyleHistory:
    fret: pd.DataFrame     # days x FACTORS daily factor returns
    resid: pd.DataFrame    # days x ticker daily specific returns (float32)


def fit_history(expo: dict[pd.Timestamp, pd.DataFrame], signal_days: pd.Series, daily_ret: pd.DataFrame,
                ridge: float = 1e-4) -> StyleHistory:
    """expo[m]: DataFrame indexed by ticker, columns FACTORS + 'w' (WLS weight), built with data <= signal_days[m].
    signal_days: month-end -> last trading day <= month-end. A day d uses the latest m with signal_days[m] < d."""
    ms = sorted(expo)
    sig = pd.DatetimeIndex([signal_days[m] for m in ms])
    days = daily_ret.index
    f_rows, f_idx = [], []
    res = np.full(daily_ret.shape, np.nan, dtype="float32")
    col_pos = {c: i for i, c in enumerate(daily_ret.columns)}
    R_all = daily_ret.to_numpy(dtype=float)
    cache_m = None
    for k, d in enumerate(days):
        j = int(np.searchsorted(sig.to_numpy(), np.datetime64(d), side="left")) - 1
        if j < 0:
            continue
        m = ms[j]
        if m != cache_m:
            E = expo[m]
            Xm = E[FACTORS].to_numpy(dtype=float)
            wm = E["w"].to_numpy(dtype=float)
            pos = np.array([col_pos.get(t, -1) for t in E.index])
            cache_m = m
        r = np.where(pos >= 0, R_all[k, np.maximum(pos, 0)], np.nan)
        ok = np.isfinite(r)
        if ok.sum() < 100:
            continue
        sw = np.sqrt(wm[ok])
        A = Xm[ok] * sw[:, None]
        y = r[ok] * sw
        f = np.linalg.solve(A.T @ A + ridge * np.eye(A.shape[1]), A.T @ y)
        e = r[ok] - Xm[ok] @ f
        res[k, pos[ok]] = e.astype("float32")
        f_rows.append(f)
        f_idx.append(d)
    fret = pd.DataFrame(f_rows, index=pd.DatetimeIndex(f_idx), columns=FACTORS)
    return StyleHistory(fret, pd.DataFrame(res, index=days, columns=daily_ret.columns))


def model_at(hist: StyleHistory, sig_day: pd.Timestamp, X: pd.DataFrame, window: int = 252,
             blend: float = 0.7, min_spec_obs: int = 60) -> dict:
    """Risk model for a signal at `sig_day` using ONLY factor returns and residuals dated <= sig_day.
    X: tickers x FACTORS exposures at the signal bar. Returns L (n x k, daily units: Sigma = L L' + diag(d))."""
    f = hist.fret.loc[:sig_day].iloc[-window:]
    if len(f) < 100:
        raise ValueError("not enough factor-return history")
    keep = f.std() > 1e-10
    cols = [c for c in FACTORS if keep[c]]
    F = LedoitWolf().fit(f[cols].to_numpy()).covariance_
    w, V = np.linalg.eigh(F)
    C = V * np.sqrt(np.clip(w, 0, None))
    Xs = X[cols].to_numpy(dtype=float)
    L = Xs @ C
    e = hist.resid.loc[:sig_day].iloc[-window:].reindex(columns=X.index)
    cnt = e.notna().sum()
    own = e.var(ddof=1).where(cnt >= min_spec_obs)
    med = float(np.nanmedian(own)) if own.notna().any() else float(np.nanmedian(e.var()))
    d = (blend * own.fillna(med) + (1 - blend) * med).to_numpy(dtype=float)
    d = np.maximum(d, 1e-8)
    return {"L": L, "d": d, "F": F, "cols": cols, "X": Xs}


def variance_split(w: np.ndarray, m: dict) -> dict:
    """Daily variance split of a book into industry, style and specific parts (cross = industry/style covariance)."""
    cols = m["cols"]
    expo = m["X"].T @ w
    F = m["F"]
    ind = np.array([c.startswith("ind") for c in cols])
    Fi, Fs = F * np.outer(ind, ind), F * np.outer(~ind, ~ind)
    v_ind, v_sty = float(expo @ Fi @ expo), float(expo @ Fs @ expo)
    v_tot_f = float(expo @ F @ expo)
    v_spec = float(np.sum(m["d"] * w**2))
    return {"industry": v_ind, "style": v_sty, "cross": v_tot_f - v_ind - v_sty, "specific": v_spec,
            "total": v_tot_f + v_spec}
