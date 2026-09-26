"""Monthly walk-forward backtest of all pre-specified books.

At each month-end t (signal bar = last trading day <= t):
  1. universe: non-financial NYSE/Nasdaq stocks, raw price >= $5, >= 252 days of history,
     >= 3 of 5 themes available, top-N by market cap;
  2. risk model from the trailing 252 trading days (<= signal bar);
  3. scores for every peer scheme; alpha = IC * idio-vol * score;
  4. each book optimised from its drifted previous weights;
  5. positions filled at the t+1 close and held to the next month's t+1 close (ret_fwd).
Nothing dated after the signal bar enters steps 1-4 (enforced by tests/test_lookahead.py).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from peerrel import risk
from peerrel.portfolio import OptConfig, optimise, trade_cost
from peerrel.signals.peers import SCHEMES, resolve_small_groups, return_clusters
from peerrel.signals.scores import THEMES, composite, decompose, theme_scores

PEER_SCHEMES = ["FF12", "FF49", "SIC3", "RCLUST"]


@dataclass
class BacktestConfig:
    universe_size: int = 1000
    min_price: float = 5.0
    ic: float = 0.03
    borrow_bps: float = 25.0
    cost_multiplier: float = 1.0
    n_clusters: int = 50
    exclude_characteristics: list[str] = field(default_factory=list)   # robustness, e.g. ["mom_12_1"]
    books: list[str] = field(default_factory=lambda: (
        ["C_ALL"] + [f"C_{s}" for s in PEER_SCHEMES] + [f"CN_{s}" for s in PEER_SCHEMES]
        + [f"W_{s}" for s in PEER_SCHEMES] + [f"B_{s}" for s in PEER_SCHEMES]))


def eligible(x: pd.DataFrame, cfg: BacktestConfig) -> pd.DataFrame:
    sic = x["sic"]
    ok = (x["raw_close"] >= cfg.min_price) & (x["n_obs"] >= 252) & (x["adv_63d"] > 0) \
        & x["mcap"].notna() & ~sic.between(6000, 6999) & sic.notna()
    return x[ok]


def book_signal(book: str, x: pd.DataFrame, labels: dict[str, pd.Series]) -> tuple[pd.Series, str | None]:
    """Return (score, neutralisation scheme or None) for a book name like 'C_FF49'."""
    kind, scheme = book.split("_", 1)
    if kind == "C":
        grp = None if scheme == "ALL" else labels[scheme]
        return composite(theme_scores(x, grp)), None
    if kind == "CN":
        return composite(theme_scores(x, labels[scheme])), scheme
    raw = composite(theme_scores(x, None))
    parts = decompose(raw.dropna(), labels[scheme].loc[raw.dropna().index])
    s = parts["within" if kind == "W" else "between"]
    sd = s.std(ddof=0)
    if not np.isfinite(sd) or sd < 1e-8:          # e.g. a single peer group: no between-signal
        return pd.Series(0.0, index=s.index), None
    return (s - s.mean()) / sd, None


class Backtest:
    def __init__(self, panel: pd.DataFrame, daily_ret: pd.DataFrame, ff_daily: pd.DataFrame,
                 ff_monthly: pd.DataFrame, months: pd.DataFrame, static_groups: pd.DataFrame,
                 opt: OptConfig, cfg: BacktestConfig):
        self.panel, self.daily_ret, self.ffd, self.ffm = panel, daily_ret, ff_daily, ff_monthly
        self.months = months.set_index("date")
        self.static_groups, self.opt, self.cfg = static_groups, opt, cfg
        self.clusters: dict[int, pd.Series] = {}

    # ------------------------------------------------------------------ helpers
    def _cluster_labels(self, t: pd.Timestamp, rm: risk.RiskModel, tick_to_cik: pd.Series) -> pd.Series:
        """Clusters are fitted at each December signal bar and used for the NEXT 12 months."""
        if t.month == 12:
            lab = return_clusters(rm.resid, k=self.cfg.n_clusters)
            self.clusters[t.year] = lab.rename(index=tick_to_cik)
        use_year = max([y for y in self.clusters if y < t.year], default=None)
        return self.clusters.get(use_year, pd.Series(dtype=float))

    def _universe(self, t: pd.Timestamp) -> pd.DataFrame:
        cfg = self.cfg
        x = eligible(self.panel.loc[t], cfg).drop(columns=cfg.exclude_characteristics, errors="ignore")
        themes_raw = theme_scores(x, None)
        x = x[themes_raw.notna().sum(axis=1) >= 3]
        return x.nlargest(cfg.universe_size, "mcap")

    def _warmup_clusters(self, dec: pd.Timestamp) -> None:
        """Fit return clusters at a December before the first backtest month (no trading)."""
        x = self._universe(dec)
        sig_day = self.months.loc[dec, "signal_day"]
        window = self.daily_ret.loc[:sig_day].iloc[-252:].reindex(columns=x["ticker"])
        rm = risk.estimate(window, self.ffd["Mkt-RF"], self.ffd["RF"])
        tick_to_cik = pd.Series(x.index, index=x["ticker"].to_numpy())
        self._cluster_labels(dec, rm, tick_to_cik)

    def run(self, dates: list[pd.Timestamp], out_dir: Path) -> pd.DataFrame:
        out_dir.mkdir(parents=True, exist_ok=True)
        cfg, opt = self.cfg, self.opt
        prev_w = {b: pd.Series(dtype=float) for b in cfg.books}
        rows, weights, ics = [], [], []
        t0 = time.time()
        warm = pd.Timestamp(year=dates[0].year - 1, month=12, day=31)
        if warm not in dates and warm in self.months.index:
            self._warmup_clusters(warm)
        for i, t in enumerate(dates):
            sig_day = self.months.loc[t, "signal_day"]
            x = eligible(self.panel.loc[t], cfg).drop(columns=cfg.exclude_characteristics, errors="ignore")
            themes_raw = theme_scores(x, None)
            x = x[themes_raw.notna().sum(axis=1) >= 3]
            x = x.nlargest(cfg.universe_size, "mcap")
            tick_to_cik = pd.Series(x.index, index=x["ticker"].to_numpy())

            window = self.daily_ret.loc[:sig_day].iloc[-252:]
            window = window.reindex(columns=x["ticker"])
            rm = risk.estimate(window, self.ffd["Mkt-RF"], self.ffd["RF"])
            x = x[x["ticker"].isin(rm.tickers)]
            order = pd.Index(x["ticker"])
            pos = rm.tickers.get_indexer(order)
            beta, L, d = rm.beta[pos], rm.L[pos], rm.d[pos]

            groups = self.static_groups.reindex(x.index).copy()
            groups["RCLUST"] = self._cluster_labels(t, rm, tick_to_cik).reindex(x.index)
            labels = {s: resolve_small_groups(groups, s) for s in PEER_SCHEMES}

            idio_m = np.sqrt(d * 21)
            hs = (x["spread"].fillna(x["spread"].median()).clip(lower=0.0002) / 2).to_numpy() * cfg.cost_multiplier
            vol_d = x["vol_63d"].fillna(x["vol_63d"].median()).to_numpy()
            adv = x["adv_63d"].to_numpy()
            r = x["ret_fwd"]
            n_missing_ret = int(r.isna().sum())
            r = r.fillna(0.0).to_numpy()
            rf_next = float(self.ffm["RF"].get(t + pd.offsets.MonthEnd(1), np.nan))

            # diagnostics: rank IC of themes and composite versus the forward return
            if r.std() > 0:
                sc = themes_raw.reindex(x.index).assign(composite=composite(themes_raw.reindex(x.index)))
                ic = sc.corrwith(pd.Series(r, index=x.index), method="spearman")
                ics.append(ic.rename(t))

            for b in cfg.books:
                s, neutral = book_signal(b, x, labels)
                s = s.reindex(x.index).fillna(0.0).to_numpy()
                alpha = cfg.ic * idio_m * s
                w0 = prev_w[b].reindex(order).fillna(0.0).to_numpy()
                exit_w = prev_w[b].drop(order, errors="ignore")
                H = None
                if neutral:
                    H = pd.get_dummies(labels[neutral]).to_numpy(dtype=float)
                w = optimise(alpha, beta, L, d, w0, hs, vol_d, adv, opt, H)
                dw = w - w0
                c = trade_cost(dw, hs, vol_d, adv, opt) * cfg.cost_multiplier
                c += float((np.abs(exit_w) * 0.002).sum())          # forced exits at a flat 20 bp
                gross_pnl = float(w @ r)
                net_dollar = float(w.sum())
                borrow = cfg.borrow_bps / 1e4 / 12 * float(-w[w < 0].sum())
                excess = gross_pnl - net_dollar * (rf_next if np.isfinite(rf_next) else 0.0) - borrow - c
                rows.append({"date": t, "book": b, "excess_ret": excess, "gross_ret": gross_pnl,
                             "cost": c, "borrow": borrow, "turnover": float(np.abs(dw).sum()) / 2,
                             "gross_exposure": float(np.abs(w).sum()), "net_dollar": net_dollar,
                             "n_long": int((w > 0).sum()), "n_short": int((w < 0).sum()),
                             "exante_vol": float(np.sqrt(np.sum((L.T @ w) ** 2) + np.sum(d * w**2)) * np.sqrt(252)),
                             "beta_exante": float(beta @ w), "n_universe": len(order),
                             "n_missing_ret": n_missing_ret, "rf": rf_next})
                held = pd.Series(w, index=order)
                held = held[held != 0]
                weights.append(pd.DataFrame({"date": t, "book": b, "ticker": held.index, "w": held.to_numpy()}))
                # drift to next month's pre-trade weights
                nav = 1.0 + gross_pnl
                prev_w[b] = held * (1 + pd.Series(r, index=order).reindex(held.index)) / nav
            print(f"\r{i + 1}/{len(dates)} {t.date()} n={len(order)} {time.time() - t0:.0f}s", end="", flush=True)
        print()
        res = pd.DataFrame(rows)
        res.to_parquet(out_dir / "returns.parquet", index=False)
        pd.concat(weights).to_parquet(out_dir / "weights.parquet", index=False)
        if ics:
            pd.DataFrame(ics).to_parquet(out_dir / "ic.parquet")
        (out_dir / "config.json").write_text(json.dumps({"backtest": asdict(self.cfg), "optimiser": asdict(opt),
                                                         "dates": [str(dates[0].date()), str(dates[-1].date())]},
                                                        indent=2, default=str))
        return res
