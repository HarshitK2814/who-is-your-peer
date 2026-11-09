"""v2 monthly walk-forward runner. Same month loop, universe, PCA risk model, costs and fills as v1
(src/peerrel/backtest.py); adds style-neutral rows, a turnover cap, tiered borrow and style-model risk splits.

Signal bar: month-end t (data <= t). Trades fill at the t+1 close and are held to the next month's t+1 close.
A book spec is a dict: signal (v1 book name giving the score), neutral (industry scheme or None), style (bool),
turnover (bool), borrow ('flat' = v1: 25 bp charged in accounting only; 'tiered' = in objective and accounting).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from peerrel import risk
from peerrel.backtest import PEER_SCHEMES, Backtest, book_signal, eligible
from peerrel.portfolio import trade_cost
from peerrel.signals.peers import resolve_small_groups
from peerrel.signals.scores import theme_scores
from peerrel.v2 import stylemodel as sm
from peerrel.v2.portfolio import optimise_v2, tier_borrow_bps

SPECS: dict[str, dict] = {
    "P_FF49": dict(signal="C_FF49", neutral=None, style=False, turnover=False, borrow="flat"),     # parity with v1 C_FF49
    "V0_FF49": dict(signal="C_FF49", neutral=None, style=False, turnover=False, borrow="tiered"),
    "SN_FF49": dict(signal="C_FF49", neutral=None, style=True, turnover=False, borrow="tiered"),
    "SIN_FF49": dict(signal="C_FF49", neutral="FF49", style=True, turnover=False, borrow="tiered"),
    "T_FF49": dict(signal="C_FF49", neutral=None, style=False, turnover=True, borrow="tiered"),
    "TSIN_FF49": dict(signal="C_FF49", neutral="FF49", style=True, turnover=True, borrow="tiered"),
}
NEW_BOOKS = ["V0_FF49", "SN_FF49", "SIN_FF49", "T_FF49", "TSIN_FF49"]


class BacktestV2(Backtest):
    def run_v2(self, dates: list[pd.Timestamp], out_dir: Path, specs: dict[str, dict], v2cfg: dict,
               expo_table: pd.DataFrame, hist: sm.StyleHistory) -> pd.DataFrame:
        out_dir.mkdir(parents=True, exist_ok=True)
        cfg, opt = self.cfg, self.opt
        books = list(specs)
        prev_w = {b: pd.Series(dtype=float) for b in books}
        rows, weights = [], []
        expo_by_date = {d: g.set_index("ticker") for d, g in expo_table.groupby("date")}
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

            window = self.daily_ret.loc[:sig_day].iloc[-252:].reindex(columns=x["ticker"])
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
            r = r.fillna(0.0).to_numpy()
            rf_next = float(self.ffm["RF"].get(t + pd.offsets.MonthEnd(1), np.nan))

            ex = expo_by_date[t].reindex(order)
            S = ex[sm.STYLES].fillna(0.0).to_numpy()
            tier_bps = tier_borrow_bps(x["mcap"].to_numpy(), v2cfg["borrow_tiers_bps"], v2cfg["borrow_tier_cuts"])
            smodel = None
            try:
                Xf = pd.concat([sm.industry_dummies(pd.Series(self.static_groups["FF49"].reindex(x.index).to_numpy(), index=order).astype(float)),
                                pd.DataFrame(S, index=order, columns=sm.STYLES)], axis=1)[sm.FACTORS]
                smodel = sm.model_at(hist, sig_day, Xf)
            except ValueError:
                pass

            for b in books:
                sp = specs[b]
                s, _ = book_signal(sp["signal"], x, labels)
                s = s.reindex(x.index).fillna(0.0).to_numpy()
                alpha = cfg.ic * idio_m * s
                w0 = prev_w[b].reindex(order).fillna(0.0).to_numpy()
                exit_w = prev_w[b].drop(order, errors="ignore")
                H = pd.get_dummies(labels[sp["neutral"]]).to_numpy(dtype=float) if sp["neutral"] else None
                tiered = sp["borrow"] == "tiered"
                borrow_m = tier_bps / 1e4 / 12 if tiered else None
                w, info = optimise_v2(alpha, beta, L, d, w0, hs, vol_d, adv, opt, H=H, S=S if sp["style"] else None,
                                      style_tol=v2cfg["style_tol"],
                                      turnover_cap=v2cfg["turnover_cap"] if sp["turnover"] else None,
                                      borrow_m=borrow_m)
                dw = w - w0
                c = trade_cost(dw, hs, vol_d, adv, opt) * cfg.cost_multiplier
                c += float((np.abs(exit_w) * 0.002).sum())
                gross_pnl = float(w @ r)
                net_dollar = float(w.sum())
                short = np.where(w < 0, -w, 0.0)
                borrow = float((tier_bps / 1e4 / 12) @ short) if tiered else cfg.borrow_bps / 1e4 / 12 * float(short.sum())
                excess = gross_pnl - net_dollar * (rf_next if np.isfinite(rf_next) else 0.0) - borrow - c
                row = {"date": t, "book": b, "excess_ret": excess, "gross_ret": gross_pnl, "cost": c, "borrow": borrow,
                       "turnover": float(np.abs(dw).sum()) / 2, "gross_exposure": float(np.abs(w).sum()),
                       "net_dollar": net_dollar, "n_long": int((w > 0).sum()), "n_short": int((w < 0).sum()),
                       "exante_vol": float(np.sqrt(np.sum((L.T @ w) ** 2) + np.sum(d * w**2)) * np.sqrt(252)),
                       "beta_exante": float(beta @ w), "n_universe": len(order), "rf": rf_next,
                       "opt_failed": info["failed"], "turnover_fallback": info["fallback"]}
                for k, name in enumerate(sm.STYLES):
                    row[f"expo_{name}"] = float(S[:, k] @ w)
                if smodel is not None:
                    vs = sm.variance_split(w, smodel)
                    row.update({f"var_{k}": v * 21 for k, v in vs.items()})
                    row["exante_vol_style_model"] = float(np.sqrt(vs["total"] * 252))
                rows.append(row)
                held = pd.Series(w, index=order)
                held = held[held != 0]
                weights.append(pd.DataFrame({"date": t, "book": b, "ticker": held.index, "w": held.to_numpy()}))
                nav = 1.0 + gross_pnl
                prev_w[b] = held * (1 + pd.Series(r, index=order).reindex(held.index)) / nav
            print(f"\r{i + 1}/{len(dates)} {t.date()} n={len(order)} {time.time() - t0:.0f}s", end="", flush=True)
        print()
        res = pd.DataFrame(rows)
        res.to_parquet(out_dir / "returns.parquet", index=False)
        pd.concat(weights).to_parquet(out_dir / "weights.parquet", index=False)
        (out_dir / "config.json").write_text(json.dumps({"backtest": asdict(self.cfg), "optimiser": asdict(opt),
                                                         "v2": v2cfg, "specs": specs,
                                                         "dates": [str(dates[0].date()), str(dates[-1].date())]},
                                                        indent=2, default=str))
        return res
