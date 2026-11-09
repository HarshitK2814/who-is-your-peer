import numpy as np

from peerrel.portfolio import OptConfig, optimise
from peerrel.v2.portfolio import optimise_v2, tier_borrow_bps


def _problem(n=60, k=3, seed=0):
    rng = np.random.default_rng(seed)
    return dict(alpha=rng.normal(0, 0.01, n), beta=rng.uniform(0.6, 1.4, n), L=rng.normal(0, 0.003, (n, k)),
                d=np.full(n, 1e-4), half_spread=np.full(n, 0.0005), daily_vol=np.full(n, 0.02),
                adv=np.full(n, 5e7))


CFG = OptConfig(risk_aversion=8, gross=2.0, name_cap=0.05, adv_cap=0.05, nav=1e8)


def test_parity_with_v1_when_options_off():
    p = _problem()
    w0 = np.zeros(60)
    a = optimise(p["alpha"], p["beta"], p["L"], p["d"], w0, p["half_spread"], p["daily_vol"], p["adv"], CFG)
    b, info = optimise_v2(p["alpha"], p["beta"], p["L"], p["d"], w0, p["half_spread"], p["daily_vol"], p["adv"], CFG)
    assert np.allclose(a, b, atol=1e-6) and not info["failed"]


def test_style_rows_and_turnover_cap_hold():
    p = _problem()
    rng = np.random.default_rng(3)
    S = rng.normal(size=(60, 4))
    w0 = np.zeros(60)
    w1, _ = optimise_v2(p["alpha"], p["beta"], p["L"], p["d"], w0, p["half_spread"], p["daily_vol"], p["adv"], CFG, S=S,
                        style_tol=0.02)
    assert np.all(np.abs(S.T @ w1) <= 0.02 + 1e-6)
    w2, info = optimise_v2(p["alpha"], p["beta"], p["L"], p["d"], w1, p["half_spread"], p["daily_vol"], p["adv"], CFG, S=S,
                           style_tol=0.02, turnover_cap=0.05)
    assert not info["fallback"] and np.abs(w2 - w1).sum() / 2 <= 0.05 + 1e-6


def test_infeasible_cap_falls_back_and_flags():
    p = _problem()
    w0 = np.where(np.arange(60) % 2 == 0, 0.04, -0.04) * 1.0       # beta-unbalanced start, tight cap cannot fix it
    w, info = optimise_v2(p["alpha"], p["beta"], p["L"], p["d"], w0, p["half_spread"], p["daily_vol"], p["adv"], CFG,
                          turnover_cap=1e-4)
    assert info["fallback"] and not info["failed"] and abs(p["beta"] @ w) < 1e-6


def test_borrow_cost_discourages_shorting_a_name():
    p = _problem()
    w0 = np.zeros(60)
    base, _ = optimise_v2(p["alpha"], p["beta"], p["L"], p["d"], w0, p["half_spread"], p["daily_vol"], p["adv"], CFG)
    heavy = np.zeros(60)
    heavy[:30] = 0.05                                    # 5% a month on half the names
    w, _ = optimise_v2(p["alpha"], p["beta"], p["L"], p["d"], w0, p["half_spread"], p["daily_vol"], p["adv"], CFG,
                       borrow_m=heavy)
    assert -w[:30][w[:30] < 0].sum() < -base[:30][base[:30] < 0].sum()


def test_tier_borrow_by_mcap_rank():
    mcap = np.arange(1, 1001, dtype=float)               # rank 1 = largest = index 999
    b = tier_borrow_bps(mcap, [25, 50, 150], [500, 800])
    assert b[999] == 25 and b[500] == 25 and b[499] == 50 and b[200] == 50 and b[199] == 150 and b[0] == 150
    assert (b == 25).sum() == 500 and (b == 50).sum() == 300 and (b == 150).sum() == 200
