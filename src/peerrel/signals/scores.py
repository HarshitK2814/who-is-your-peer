"""Characteristic -> peer-relative score -> theme -> composite, and the within/between split.

All functions operate on ONE cross-section (a single month-end); the backtest calls them
date by date, so no information can cross dates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

# [Reconstruction] mapping of the five disclosed themes to published characteristics.
THEMES: dict[str, list[str]] = {
    "quality": ["gp_to_assets", "accruals_neg", "leverage_neg", "cf_stability"],
    "management": ["ext_financing_neg", "share_issuance_neg", "asset_growth_neg"],
    "growth": ["eps_persistence", "sales_growth"],
    "sentiment": ["mom_12_1", "sue"],
    "valuation": ["earnings_yield", "book_to_market", "cfo_yield", "sales_yield"],
}
CHARACTERISTICS = [c for cs in THEMES.values() for c in cs]


def winsorize(x: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    ql, qh = x.quantile([lo, hi])
    return x.clip(ql, qh)


def rank_gaussian(x: pd.Series, groups: pd.Series | None = None) -> pd.Series:
    """Phi^{-1}((rank - 0.5) / N) within each group; NaNs stay NaN and are not counted."""
    if groups is None:
        groups = pd.Series(0, index=x.index)
    r = x.groupby(groups).rank(method="average")
    n = x.notna().groupby(groups).transform("sum")
    return pd.Series(norm.ppf((r - 0.5) / n), index=x.index)


def zscore(x: pd.Series) -> pd.Series:
    return (x - x.mean()) / x.std(ddof=0)


def theme_scores(chars: pd.DataFrame, groups: pd.Series | None) -> pd.DataFrame:
    z = pd.DataFrame({c: rank_gaussian(winsorize(chars[c]), groups) for c in CHARACTERISTICS if c in chars})
    return pd.DataFrame({t: zscore(z[[c for c in cs if c in z]].mean(axis=1)) for t, cs in THEMES.items()})


def composite(themes: pd.DataFrame, min_themes: int = 3) -> pd.Series:
    s = themes.mean(axis=1).where(themes.notna().sum(axis=1) >= min_themes)
    return zscore(s)


def decompose(raw_composite: pd.Series, groups: pd.Series) -> pd.DataFrame:
    """S = W + B with B = peer-group mean of the raw (non-peer-normalised) composite."""
    b = raw_composite.groupby(groups).transform("mean")
    return pd.DataFrame({"within": raw_composite - b, "between": b})
