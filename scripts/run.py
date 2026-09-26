"""Pipeline entry point.

    python scripts/run.py download        # SEC bulk + Ken French (+ prices)
    python scripts/run.py build           # facts -> period characteristics -> monthly panel
    python scripts/run.py calibrate       # risk aversion on development months (writes backtest.yaml)
    python scripts/run.py backtest --period development,validation
    python scripts/run.py backtest --period test,recent   # needs PREREG_HASH (see qcore.splits)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qcore.splits import Splits, guard  # noqa: E402

from peerrel.config import INTERIM, PROCESSED, RESEARCH, RESULTS, ROOT  # noqa: E402

PREREG = RESEARCH / "preregistration.md"


def step_download() -> None:
    from peerrel.data import download, prices, sec_meta
    download.download_french()
    download.download_sec()
    comp = sec_meta.build_company_table()
    prices.download_all(comp["ticker"].tolist())
    prices.build_daily_panel()


def step_build() -> None:
    from peerrel.data import xbrl
    from peerrel.features import fundamentals, panel
    facts_path = INTERIM / "xbrl_facts.parquet"
    if not facts_path.exists():
        xbrl.build_facts()
    facts = pd.read_parquet(facts_path)
    comp = pd.read_parquet(INTERIM / "companies.parquet")
    facts = facts[facts["cik"].isin(comp["cik"])]
    print(f"facts for universe: {len(facts):,} rows, {facts['cik'].nunique():,} companies")
    period = fundamentals.period_characteristics(facts)
    period.to_parquet(INTERIM / "period_characteristics.parquet")
    px = pd.read_parquet(INTERIM / "daily_prices.parquet")
    p = panel.build_panel(period, px, comp)
    p.to_parquet(PROCESSED / "panel.parquet")
    print("panel", p.shape)


def _load_backtest(cfg_over: dict | None = None):
    from peerrel.backtest import Backtest, BacktestConfig
    from peerrel.data.french import factors
    from peerrel.features.panel import month_end_map, trading_calendar
    from peerrel.portfolio import OptConfig
    from peerrel.signals.peers import static_peers

    conf = yaml.safe_load((ROOT / "configs" / "backtest.yaml").read_text())
    conf.update(cfg_over or {})
    opt_conf = conf.pop("optimiser")
    panel = pd.read_parquet(PROCESSED / "panel.parquet")
    px = pd.read_parquet(INTERIM / "daily_prices.parquet", columns=["date", "ticker", "ret"])
    daily_ret = px.pivot(index="date", columns="ticker", values="ret").astype("float32")
    cal = trading_calendar(px)
    months = month_end_map(cal, "2010-01-31", str(cal[-1].date()))
    comp = pd.read_parquet(INTERIM / "companies.parquet")
    groups = static_peers(comp)
    bt = Backtest(panel, daily_ret, factors(daily=True), factors(daily=False), months, groups,
                  OptConfig(**opt_conf), BacktestConfig(**conf))
    return bt, panel


def _dates(panel: pd.DataFrame, periods: list[str]) -> list[pd.Timestamp]:
    splits = Splits.from_dict(yaml.safe_load((ROOT / "configs" / "splits.yaml").read_text()))
    all_dates = panel.index.get_level_values("date").unique().sort_values()
    has_fwd = panel["ret_fwd"].notna().groupby(level="date").any()
    out = []
    for p in periods:
        guard(p, PREREG)
        lo, hi = splits.bounds(p)
        out += [d for d in all_dates if lo <= d <= hi and has_fwd.get(d, False)]
    return sorted(out)


def step_calibrate(target_vol: float = 0.03) -> None:
    """Pick risk aversion so the median ex-ante vol of the C_FF49 book ~= target, using every 4th
    development month only (ex-ante risk only; no realised returns are looked at). Target 3%: with
    gross exposure capped at 200%, a diversified beta-neutral book tops out near 3.5% ex-ante vol,
    so 3% keeps the risk penalty (not the gross cap) in control."""
    conf_path = ROOT / "configs" / "backtest.yaml"
    grid = [2, 4, 8, 16, 32, 64, 128]
    results = {}
    for lam in grid:
        bt, panel = _load_backtest()
        bt.opt.risk_aversion = lam
        bt.cfg.books = ["C_FF49"]
        dates = _dates(panel, ["development"])[::4]
        res = bt.run(dates, RESULTS / "runs" / "calibration" / f"lam_{lam}")
        results[lam] = float(res["exante_vol"].median())
        print(f"lambda={lam}: median ex-ante vol {results[lam]:.3%}, median gross {res['gross_exposure'].median():.2f}")
    best = min(results, key=lambda l: abs(np.log(results[l] / target_vol)))
    conf = yaml.safe_load(conf_path.read_text())
    conf["optimiser"]["risk_aversion"] = best
    conf_path.write_text(yaml.safe_dump(conf, sort_keys=False))
    pd.Series(results, name="median_exante_vol").to_csv(RESULTS / "tables" / "calibration_lambda.csv")
    print("chosen risk_aversion:", best)


def step_backtest(periods: list[str], tag: str, overrides: dict | None = None) -> None:
    bt, panel = _load_backtest(overrides)
    dates = _dates(panel, periods)
    run_id = f"{datetime.now():%Y%m%d-%H%M}_{tag}"
    bt.run(dates, RESULTS / "runs" / run_id)
    print("run:", run_id)


def step_paper(signal_date: str) -> None:
    """Simulated live evaluation (no real capital). Run AFTER the close of month-end `signal_date`
    and BEFORE the next trading day; commit paper_trading/<YYYY-MM>/ immediately so the git
    timestamp proves the weights preceded the outcome. Requires re-running `download` and
    `build` first so the panel contains `signal_date`."""
    t = pd.Timestamp(signal_date) + pd.offsets.MonthEnd(0)
    bt, panel = _load_backtest()
    dec = pd.Timestamp(year=t.year - 1, month=12, day=31)
    dates = [d for d in panel.index.get_level_values("date").unique().sort_values() if dec <= d <= t]
    if not dates or dates[-1] != t:
        raise SystemExit(f"panel has no data for {t.date()} — rerun download/build after the month-end close")
    out = ROOT / "paper_trading" / f"{t:%Y-%m}"
    bt.run(dates, RESULTS / "runs" / f"paper_{t:%Y%m}")
    w = pd.read_parquet(RESULTS / "runs" / f"paper_{t:%Y%m}" / "weights.parquet")
    out.mkdir(parents=True, exist_ok=True)
    w[w["date"] == t].to_csv(out / "weights.csv", index=False)
    (out / "README.md").write_text(
        f"# Paper portfolio formed on {t.date()}\n\nSimulated live evaluation, not real trading. Weights were "
        f"generated after the {t.date()} close for execution at the next close. Outcome is recorded "
        f"after the following month-end with `run.py paper-record {t:%Y-%m}`.\n")
    print("wrote", out)


def step_paper_record(month: str) -> None:
    """Append the realised (net-of-model-cost) return of a previously committed paper portfolio."""
    t = pd.Timestamp(month) + pd.offsets.MonthEnd(0)
    rets = pd.read_parquet(RESULTS / "runs" / f"paper_{t:%Y%m}" / "returns.parquet")
    panel = pd.read_parquet(PROCESSED / "panel.parquet", columns=["ticker", "ret_fwd"])
    w = pd.read_csv(ROOT / "paper_trading" / f"{t:%Y-%m}" / "weights.csv")
    realised = panel.loc[t].set_index("ticker")["ret_fwd"]
    w["ret"] = w["ticker"].map(realised)
    res = w.groupby("book").apply(lambda g: (g["w"] * g["ret"].fillna(0)).sum()).rename("gross_ret")
    costs = rets[rets["date"] == t].set_index("book")[["cost", "borrow"]]
    out = pd.concat([res, costs], axis=1)
    out["net_ret_before_financing"] = out["gross_ret"] - out["cost"] - out["borrow"]
    out.to_csv(ROOT / "paper_trading" / f"{t:%Y-%m}" / "realised.csv")
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["download", "build", "calibrate", "backtest", "paper", "paper-record"])
    ap.add_argument("--date", help="signal month for paper steps, e.g. 2026-09")
    ap.add_argument("--period", default="development,validation")
    ap.add_argument("--tag", default="main")
    ap.add_argument("--set", nargs="*", default=[], help="config overrides key=value (robustness runs)")
    a = ap.parse_args()
    over = {k: yaml.safe_load(v) for k, v in (s.split("=", 1) for s in a.set)}
    if a.step == "download":
        step_download()
    elif a.step == "build":
        step_build()
    elif a.step == "calibrate":
        step_calibrate()
    elif a.step == "paper":
        step_paper(a.date)
    elif a.step == "paper-record":
        step_paper_record(a.date)
    else:
        step_backtest(a.period.split(","), a.tag, over)
