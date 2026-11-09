import numpy as np
import pandas as pd

from peerrel.v2 import stylemodel as sm


def _world(seed=0, n=300, T=420):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2018-01-01", periods=T)
    tick = [f"T{i}" for i in range(n)]
    ind = pd.Series(rng.integers(1, 6, n), index=tick)
    D = sm.industry_dummies(ind.astype(float))
    S = pd.DataFrame(rng.normal(size=(n, 8)), index=tick, columns=sm.STYLES)
    X = pd.concat([D, S], axis=1)[sm.FACTORS]
    fr = pd.DataFrame(rng.normal(0, 0.004, (T, len(sm.FACTORS))), index=days, columns=sm.FACTORS)
    R = fr.to_numpy() @ X.to_numpy().T + rng.normal(0, 0.01, (T, n))
    ret = pd.DataFrame(R, index=days, columns=tick)
    return days, tick, X, fr, ret


def _expo(X, days):
    E = X.copy()
    E["w"] = 1.0
    ms = pd.date_range(days[0], days[-1], freq="ME")
    sigd = pd.Series({m: days[days <= m][-1] for m in ms})
    return {m: E for m in ms}, sigd


def test_factor_returns_recovered():
    days, tick, X, fr, ret = _world()
    expo, sigd = _expo(X, days)
    h = sm.fit_history(expo, sigd, ret)
    common = h.fret.index.intersection(fr.index)
    for s in ["value", "momentum", "ind2"]:
        assert np.corrcoef(h.fret.loc[common, s], fr.loc[common, s])[0, 1] > 0.9


def test_model_at_ignores_future_days():
    days, tick, X, fr, ret = _world()
    expo, sigd = _expo(X, days)
    h = sm.fit_history(expo, sigd, ret)
    cut = days[300]
    a = sm.model_at(h, cut, X)
    ret2 = ret.copy()
    ret2.loc[ret2.index > cut] *= 5.0
    b = sm.model_at(sm.fit_history(expo, sigd, ret2), cut, X)
    assert np.allclose(a["L"], b["L"]) and np.allclose(a["d"], b["d"])


def test_variance_matches_matrix_form():
    days, tick, X, fr, ret = _world()
    expo, sigd = _expo(X, days)
    m = sm.model_at(sm.fit_history(expo, sigd, ret), days[350], X)
    w = np.random.default_rng(1).normal(size=len(tick)) / len(tick)
    full = float(np.sum((m["L"].T @ w) ** 2) + np.sum(m["d"] * w**2))
    assert np.isclose(sm.variance_split(w, m)["total"], full, rtol=1e-6)


def test_style_exposures_standardised():
    rng = np.random.default_rng(2)
    n = 200
    x = pd.DataFrame({"mcap": np.exp(rng.normal(22, 1, n)), "book_to_market": rng.lognormal(-1, 0.5, n),
                      "mom_12_1": rng.normal(0.1, 0.3, n), "gp_to_assets": rng.normal(0.3, 0.1, n),
                      "leverage_neg": rng.normal(-0.4, 0.1, n), "asset_growth_neg": rng.normal(-0.1, 0.1, n),
                      "vol_63d": rng.uniform(0.01, 0.04, n)})
    x.loc[:10, "book_to_market"] = np.nan
    e = sm.style_exposures(x, pd.Series(rng.normal(1, 0.3, n), index=x.index))
    assert list(e.columns) == sm.STYLES and not e.isna().any().any()
    assert np.allclose(e["size"].mean(), 0, atol=1e-9)
