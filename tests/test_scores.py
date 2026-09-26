import numpy as np
import pandas as pd
import pytest

from peerrel.signals.peers import resolve_small_groups
from peerrel.signals.scores import composite, decompose, rank_gaussian


def test_rank_gaussian_is_centred_within_each_group():
    x = pd.Series([1, 2, 3, 10, 20, 30.0])
    g = pd.Series(["a", "a", "a", "b", "b", "b"])
    z = rank_gaussian(x, g)
    assert z.groupby(g).mean().abs().max() < 1e-12
    # identical within-group ranks -> identical scores regardless of level differences
    assert np.allclose(z[:3].to_numpy(), z[3:].to_numpy())


def test_rank_gaussian_ignores_nans():
    z = rank_gaussian(pd.Series([1.0, np.nan, 3.0]))
    assert np.isnan(z[1]) and z[0] < 0 < z[2]


def test_decomposition_identity():
    rng = np.random.default_rng(0)
    s = pd.Series(rng.normal(size=100))
    g = pd.Series(rng.integers(0, 7, size=100))
    d = decompose(s, g)
    assert np.allclose(d.sum(axis=1), s)
    assert d["within"].groupby(g).mean().abs().max() < 1e-12


def test_composite_requires_min_themes():
    t = pd.DataFrame({"a": [1.0, 1.0, 2.0, 3.0], "b": [np.nan, 0.5, 0.1, 0.3], "c": [np.nan, 0.2, 0.4, 0.9]})
    s = composite(t, min_themes=2)
    assert np.isnan(s[0]) and s[1:].notna().all()


def test_small_groups_pool_into_parent_then_all():
    groups = pd.DataFrame({
        "ALL": [0] * 14,
        "FF12": [1] * 11 + [2] * 3,
        "FF49": [5] * 5 + [6] * 3 + [7] * 3 + [8] * 3,   # 6 and 7 are small, pooled pool = 6 >= 5
    })
    lab = resolve_small_groups(groups, "FF49", min_size=5)
    assert (lab[:5] == "FF49:5").all()
    assert (lab[5:11] == "FF12:1").all()     # pooled residual of FF12 industry 1
    assert (lab[11:] == "ALL:0").all()       # FF12 industry 2 pool has only 3 -> full cross-section
