"""D1 borrow assumptions and D2 capacity (descriptive, preregistration_v2.md).
D1: flat-fee sweep and breakeven fee on the fixed v2 weights (weights not re-optimised; assumptions, not data).
D2: ADV participation per trade at $100M and a NAV sweep re-costing the fixed $100M weights with the same
square-root impact model (an UPPER BOUND on net return at larger NAV, because weights are not re-optimised).
Run: python scripts/v2/borrow_capacity.py"""

import json

import numpy as np
import pandas as pd
from common import CFG, PERIODS, TAB, hash12, load_bt, sharpe_ci, slice_period, v2_returns

from peerrel.backtest import eligible
from peerrel.signals.scores import theme_scores

BOOKS = ["V0_FF49", "SIN_FF49", "T_FF49", "TSIN_FF49"]
FLAT = [25, 50, 100, 200, 400]
NAVS = [25e6, 100e6, 250e6, 1e9, 5e9]


def recon(bt, panel, ret, W, book):
    """Per month: dw on the universe, hs, vol, adv, exit weights -> costs at several NAV. Validates against the run."""
    rb = ret[ret.book == book].set_index("date")
    wb = W[W.book == book]
    dates = sorted(rb.index)
    prev = pd.Series(dtype=float)
    imp = CFG["optimiser"]["impact_y"]
    rows, part = [], []
    for t in dates:
        x = eligible(panel.loc[t], bt.cfg)
        x = x[theme_scores(x, None).notna().sum(axis=1) >= 3].nlargest(bt.cfg.universe_size, "mcap")
        tk = x.set_index("ticker")
        w = wb[wb.date == t].set_index("ticker")["w"]
        order = tk.index.union(w.index)
        tk = tk.reindex(order)
        hs = (tk["spread"].fillna(tk["spread"].median()).clip(lower=0.0002) / 2).to_numpy()
        vol = tk["vol_63d"].fillna(tk["vol_63d"].median()).to_numpy()
        adv = tk["adv_63d"].fillna(tk["adv_63d"].median()).to_numpy()
        w0 = prev.reindex(order).fillna(0.0).to_numpy()
        w1 = w.reindex(order).fillna(0.0).to_numpy()
        exit_w = prev.drop(order, errors="ignore")
        dw = w1 - w0
        short_gross = float(-w1[w1 < 0].sum())
        base = hs @ np.abs(dw)
        coef = imp * vol * np.sqrt(1.0 / np.maximum(adv, 1.0))      # multiply by sqrt(NAV)
        exits = 0.002 * float(np.abs(exit_w).sum())
        costs = {nav: float(base + (coef * np.sqrt(nav)) @ np.abs(dw) ** 1.5 + exits) for nav in NAVS}
        nav0 = CFG["optimiser"]["nav"]
        tr = np.abs(dw) > 1e-6
        rows.append({"date": t, "short_gross": short_gross, "cost_recon_100M": costs[nav0], "cost_run": rb.loc[t, "cost"],
                     **{f"cost_{int(n / 1e6)}M": c for n, c in costs.items()},
                     "pos_over_5pct_adv_100M": float((np.abs(w1) * nav0 > 0.05 * adv).mean() if len(w1) else 0),
                     **{f"gross_over_adv5_{int(n / 1e6)}M": float(np.abs(w1)[np.abs(w1) * n > 0.05 * adv].sum() / max(np.abs(w1).sum(), 1e-12)) for n in NAVS}})
        for n in NAVS:
            p = np.abs(dw[tr]) * n / adv[tr]
            part.append(pd.DataFrame({"date": t, "nav": n, "part": p}))
        # drift
        r = panel.loc[t].set_index("ticker")["ret_fwd"].reindex(w.index).fillna(0.0)
        prev = w * (1 + r) / (1 + rb.loc[t, "gross_ret"])
    return pd.DataFrame(rows).set_index("date"), pd.concat(part)


def main():
    bt, panel = load_bt()
    ret = v2_returns()
    W = pd.read_parquet(TAB.parent / "runs" / "v2_main" / "weights.parquet")
    out = {"prereg_hash": hash12(), "assumption": "borrow tiers and flat fees are assumptions (no free stock-loan data)",
           "books": {}}
    fee_rows, nav_rows, part_rows = [], [], []
    for book in BOOKS:
        rb = ret[ret.book == book].set_index("date")
        R, part = recon(bt, panel, ret, W, book)
        err = float((R["cost_recon_100M"] - R["cost_run"]).abs().max())
        out["books"][book] = {"max_abs_cost_recon_error": err}
        for plabel, (lo, hi) in PERIODS.items():
            ex = slice_period(rb["excess_ret"], lo, hi)
            sg = slice_period(R["short_gross"], lo, hi)
            base = ex + slice_period(rb["borrow"], lo, hi)             # excess before borrow
            for f in FLAT:
                r = base - f / 1e4 / 12 * sg
                s, a, c = sharpe_ci(r, 1000)
                fee_rows.append({"book": book, "period": plabel, "borrow": f"flat {f} bp", "months": len(r),
                                 "mean_excess_ann_pct": 1200 * r.mean(), "sharpe": s, "ci_lo": a, "ci_hi": c})
            s, a, c = sharpe_ci(ex, 1000)
            fee_rows.append({"book": book, "period": plabel, "borrow": "tiered 25/50/150", "months": len(ex),
                             "mean_excess_ann_pct": 1200 * ex.mean(), "sharpe": s, "ci_lo": a, "ci_hi": c})
            be = float(base.mean() / (sg / 12).mean() * 1e4)
            out["books"][book].setdefault("breakeven_flat_fee_bp", {})[plabel] = be
            c100 = slice_period(R["cost_100M"], lo, hi)
            s100 = None
            for n in NAVS:
                cn = slice_period(R[f"cost_{int(n / 1e6)}M"], lo, hi)
                r = ex + c100 - cn
                s, a, c = sharpe_ci(r, 1000)
                if n == 100e6:
                    s100 = s
                nav_rows.append({"book": book, "period": plabel, "nav_musd": n / 1e6, "months": len(r),
                                 "mean_excess_ann_pct": 1200 * r.mean(), "sharpe": s, "ci_lo": a, "ci_hi": c,
                                 "cost_bps_yr": 1e4 * 12 * cn.mean(),
                                 "gross_share_in_positions_over_5pct_adv": float(slice_period(R[f"gross_over_adv5_{int(n / 1e6)}M"], lo, hi).mean())})
            sub = pd.DataFrame([x for x in nav_rows if x["book"] == book and x["period"] == plabel])
            ok = sub[sub.sharpe >= s100 - 0.10]
            out["books"][book].setdefault("capacity_musd_sharpe_within_0.10_of_100M", {})[plabel] = float(ok.nav_musd.max())
        for n in NAVS:
            g = part[part.nav == n]["part"]
            part_rows.append({"book": book, "nav_musd": n / 1e6, "trades": int(len(g)), "median_pct_adv": 100 * g.median(),
                              "p95_pct_adv": 100 * g.quantile(0.95), "share_over_5pct": float((g > 0.05).mean()),
                              "share_over_20pct": float((g > 0.20).mean())})
    pd.DataFrame(fee_rows).to_csv(TAB / "borrow_sweep.csv", index=False)
    pd.DataFrame(nav_rows).to_csv(TAB / "capacity_nav_sweep.csv", index=False)
    pd.DataFrame(part_rows).to_csv(TAB / "adv_participation.csv", index=False)
    (TAB / "borrow_capacity.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
