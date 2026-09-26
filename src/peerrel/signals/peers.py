"""Peer-group definitions.

Free-data substitute for Hoberg-Phillips TNIC (whose free files are keyed by Compustat
gvkey, which cannot be linked to SEC CIKs without paid data):
  * SIC3  - three-digit SIC, the granularity TNIC-3 is calibrated to match;
  * RCLUST - statistical peers: clusters of stocks with correlated residual returns,
             re-estimated each December from the *preceding* 252 trading days only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering

from peerrel.data.french import assign_industry

SCHEMES = ["ALL", "FF12", "FF49", "SIC3", "RCLUST"]
PARENT = {"FF49": "FF12", "SIC3": "FF49", "FF12": "ALL", "RCLUST": "ALL", "ALL": None}


def static_peers(companies: pd.DataFrame) -> pd.DataFrame:
    """cik -> group id for the SIC-based schemes (current SIC; see limitations)."""
    sic = companies.set_index("cik")["sic"].astype("float")
    return pd.DataFrame({
        "ALL": pd.Series(0, index=sic.index),
        "FF12": assign_industry(sic, 12),
        "FF49": assign_industry(sic, 49),
        "SIC3": (sic // 10).astype("Int64"),
    })


def return_clusters(daily_resid: pd.DataFrame, k: int = 50, min_obs: int = 200) -> pd.Series:
    """Ward clustering of standardised residual-return series (Euclidean distance between
    z-scored series is a monotone function of correlation distance)."""
    r = daily_resid.dropna(axis=1, thresh=min_obs)
    r = r.fillna(0.0)
    z = (r - r.mean()) / r.std(ddof=0).replace(0, np.nan)
    z = z.dropna(axis=1)
    if z.shape[1] < k:
        return pd.Series(0, index=z.columns)
    labels = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(z.T.to_numpy())
    return pd.Series(labels, index=z.columns)


def resolve_small_groups(groups: pd.DataFrame, scheme: str, min_size: int = 5) -> pd.Series:
    """Stocks in groups with < min_size members are pooled into a residual group labelled by
    their parent-scheme group; if that pool is still too small it moves up again, ending at
    the full cross-section. `groups`: rows = stocks at one date, columns = schemes."""
    label = groups[scheme].astype("string").radd(f"{scheme}:")
    s = scheme
    while True:
        counts = label.map(label.value_counts())
        small = counts < min_size
        parent = PARENT[s]
        if not small.any() or parent is None:
            break
        label[small] = groups.loc[small, parent].astype("string").radd(f"{parent}:")
        s = parent
    return label.fillna("ALL:0")
