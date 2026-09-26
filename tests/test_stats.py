import numpy as np
import pandas as pd

from peerrel.stats import romano_wolf, sharpe_diff_hac, spanning


def test_sharpe_diff_zero_for_identical_series():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.01, 0.03, 200))
    res = sharpe_diff_hac(r, r.copy())
    assert abs(res["diff_ann"]) < 1e-12


def test_sharpe_diff_detects_large_difference():
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 0.03, 600)
    good, bad = pd.Series(0.02 + noise), pd.Series(-0.01 + noise + rng.normal(0, 0.01, 600))
    assert sharpe_diff_hac(good, bad)["p_two_sided"] < 0.01


def test_romano_wolf_rejects_only_true_effects():
    rng = np.random.default_rng(2)
    df = pd.DataFrame({"real": rng.normal(0.02, 0.03, 300), "null1": rng.normal(0, 0.03, 300),
                       "null2": rng.normal(0, 0.03, 300)})
    out = romano_wolf(df, n_boot=1000)
    assert out.loc["real", "p_rw"] < 0.01
    assert (out.loc[["null1", "null2"], "p_rw"] > 0.05).all()


def test_spanning_recovers_alpha():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2000-01-31", periods=300, freq="ME")
    f = pd.DataFrame({"MKT": rng.normal(0.005, 0.04, 300)}, index=idx)
    r = pd.Series(0.004 + 0.5 * f["MKT"] + rng.normal(0, 0.001, 300), index=idx)
    out = spanning(r, f)
    assert abs(out["alpha_ann"] - 0.048) < 0.005 and abs(out["b_MKT"] - 0.5) < 0.02
