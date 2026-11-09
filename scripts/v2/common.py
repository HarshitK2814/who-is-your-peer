"""Shared loaders for the v2 scripts (no hypothesis statistics here)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from qcore.splits import Splits, file_hash, guard  # noqa: E402

PREREG = ROOT / "research" / "preregistration_v2.md"
TAB, FIG, RUNS = ROOT / "results" / "v2" / "tables", ROOT / "results" / "v2" / "figures", ROOT / "results" / "v2" / "runs"
SEEN = "seen period (v1 reported it)"
CHOICE = ("2012-01-31", "2019-12-31")
for d in (TAB, FIG, RUNS):
    d.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PREREG_HASH", file_hash(PREREG))
CFG = yaml.safe_load((ROOT / "configs" / "backtest_v2.yaml").read_text())
SPLITS = Splits.from_dict(yaml.safe_load((ROOT / "configs" / "splits_v2.yaml").read_text()))


def hash12() -> str:
    return file_hash(PREREG)


def load_bt():
    """v1 Backtest object (data, helpers) built from the frozen v2 config (same fields as v1)."""
    from peerrel.backtest import Backtest, BacktestConfig
    from peerrel.config import INTERIM, PROCESSED
    from peerrel.data.french import factors
    from peerrel.features.panel import month_end_map, trading_calendar
    from peerrel.portfolio import OptConfig
    from peerrel.signals.peers import static_peers

    conf = {k: v for k, v in CFG.items() if k not in ("optimiser", "v2", "styles")}
    conf["borrow_bps"] = 25.0
    panel = pd.read_parquet(PROCESSED / "panel.parquet")
    px = pd.read_parquet(INTERIM / "daily_prices.parquet", columns=["date", "ticker", "ret"])
    daily_ret = px.pivot(index="date", columns="ticker", values="ret").astype("float32")
    cal = trading_calendar(px)
    months = month_end_map(cal, "2010-01-31", str(cal[-1].date()))
    comp = pd.read_parquet(INTERIM / "companies.parquet")
    bt = Backtest(panel, daily_ret, factors(daily=True), factors(daily=False), months, static_peers(comp),
                  OptConfig(**CFG["optimiser"]), BacktestConfig(**conf))
    return bt, panel


def signal_dates(panel: pd.DataFrame, lo: str, hi: str | None = None) -> list[pd.Timestamp]:
    all_dates = panel.index.get_level_values("date").unique().sort_values()
    has_fwd = panel["ret_fwd"].notna().groupby(level="date").any()
    hi_t = pd.Timestamp(hi) if hi else pd.Timestamp.max
    return [d for d in all_dates if pd.Timestamp(lo) <= d <= hi_t and has_fwd.get(d, False)]


def v1_returns() -> pd.DataFrame:
    """Wide monthly net excess returns of the 17 sealed v1 books (run 20260926-1702_full_main), indexed by signal month."""
    r = pd.read_parquet(ROOT / "results" / "runs" / "20260926-1702_full_main" / "returns.parquet")
    return r.pivot(index="date", columns="book", values="excess_ret")


def slice_period(obj, lo, hi):
    return obj.loc[(obj.index >= pd.Timestamp(lo)) & (obj.index <= pd.Timestamp(hi))]


def sharpe_ann(r) -> float:
    r = pd.Series(r).dropna()
    return float(r.mean() / r.std(ddof=1) * np.sqrt(12))


def sharpe_ci(r: pd.Series, n_boot: int = 2000, block: float = 6.0) -> tuple[float, float, float]:
    from qcore.bootstrap import bootstrap_stat, percentile_ci
    r = r.dropna()
    d = bootstrap_stat(r, sharpe_ann, n_boot=n_boot, mean_block=block)
    lo, hi = percentile_ci(d)
    return sharpe_ann(r), lo, hi


def v2_returns(tag: str = "v2_main") -> pd.DataFrame:
    """Long table of v2 book rows."""
    return pd.read_parquet(RUNS / tag / "returns.parquet")


def v2_wide(col: str = "excess_ret", tag: str = "v2_main") -> pd.DataFrame:
    return v2_returns(tag).pivot(index="date", columns="book", values=col)


PERIODS = {"design 2012-2019 (choice period)": CHOICE,
           f"2020-2026 {SEEN}": ("2020-01-31", "2026-12-31")}
