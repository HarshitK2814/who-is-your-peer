"""Data for the three 3D views on the showcase page (written to docs/showcase_3d.json).

1. Industry landscape: per month and FF49 industry, the industry mean of each raw theme score in the backtest
   universe (as known at the signal date), the industry-bet book's net weight, and the industry's NEXT-month
   value-weighted return from the Ken French 49-industry file (CRSP-based, survivorship-free).
2. Peer map: at one December signal date, the backtest's own market-model residual returns (252 days) for the
   universe, embedded in 3D by PCA of the residual correlation matrix, with FF12 sector and the return-cluster
   label the backtest used for the following year.
3. Regime surface: rolling 24-month Sharpe ratios of the within / between / composite / theme books.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import run as runner  # noqa: E402
from industry_momentum_test import industry_returns  # noqa: E402

from peerrel import risk  # noqa: E402
from peerrel.config import RESULTS, ROOT  # noqa: E402
from peerrel.data.french import sic_map  # noqa: E402
from peerrel.signals.peers import return_clusters  # noqa: E402
from peerrel.signals.scores import theme_scores  # noqa: E402

THEMES = ["quality", "management", "growth", "sentiment", "valuation"]


def rnd(v, k: int):
    """Round for JSON; missing values become null (JSON has no NaN)."""
    v = float(v)
    return None if not np.isfinite(v) else round(v, k)
PEER_MAP_DATE = pd.Timestamp("2023-12-31")


def latest_run(tag: str) -> Path:
    return sorted((RESULTS / "runs").glob(f"*_{tag}"))[-1]


def industry_landscape(bt, panel) -> dict:
    ind_ret = industry_returns()
    names = list(ind_ret.columns)
    long_names = dict(zip(sic_map(49)["industry"], sic_map(49)["name"]))
    w = pd.read_parquet(latest_run("full_main") / "weights.parquet")
    w = w[w["book"] == "B_FF49"]
    dates = sorted(pd.read_parquet(latest_run("full_main") / "returns.parquet")["date"].unique())
    frames = []
    for t in dates:
        t = pd.Timestamp(t)
        x = bt._universe(t)
        th = theme_scores(x, None)
        ff49 = bt.static_groups.reindex(x.index)["FF49"]
        df = th.assign(ind=ff49.to_numpy(), mcap=x["mcap"].to_numpy(), ticker=x["ticker"].to_numpy()).dropna(subset=["ind"])
        df["composite"] = th.reindex(df.index).mean(axis=1)
        g = df.groupby("ind")
        agg = g[THEMES + ["composite"]].mean().join(g["mcap"].sum()).join(g.size().rename("n"))
        wt = w[w["date"] == t].merge(df[["ticker", "ind"]], on="ticker").groupby("ind")["w"].sum()
        agg["weight"] = wt.reindex(agg.index).fillna(0.0)
        nxt = t + pd.offsets.MonthEnd(1)
        agg["next_ret"] = [ind_ret.loc[nxt, names[int(i) - 1]] if nxt in ind_ret.index else np.nan for i in agg.index]
        agg = agg[agg["n"] >= 3].dropna(subset=["next_ret"])
        ic = agg["composite"].corr(agg["next_ret"], method="spearman")
        frames.append({"d": t.strftime("%Y-%m"), "ic": rnd(ic, 3),
                       "rows": [[names[int(i) - 1], long_names.get(int(i), names[int(i) - 1]), int(r.n)]
                                + [rnd(r[c], 3) for c in ["sentiment", "valuation", "quality", "management", "composite"]]
                                + [rnd(r.next_ret, 4), rnd(r.weight, 4), rnd(r.mcap / 1e9, 1)]
                                for i, r in agg.iterrows()]})
    return {"cols": ["ind", "name", "n", "sentiment", "valuation", "quality", "management", "composite",
                     "next_ret", "weight", "mcap_bn"], "frames": frames}


def peer_map(bt) -> dict:
    t = PEER_MAP_DATE
    x = bt._universe(t)
    sig_day = bt.months.loc[t, "signal_day"]
    window = bt.daily_ret.loc[:sig_day].iloc[-252:].reindex(columns=x["ticker"])
    rm = risk.estimate(window, bt.ffd["Mkt-RF"], bt.ffd["RF"])
    labels = return_clusters(rm.resid, k=bt.cfg.n_clusters)          # same call the backtest makes each December
    r = rm.resid.loc[:, labels.index]
    z = ((r - r.mean()) / r.std(ddof=0)).to_numpy()
    corr = z.T @ z / len(z)
    vals, vecs = np.linalg.eigh(corr)
    order = np.argsort(vals)[::-1][:3]
    coords = vecs[:, order] * np.sqrt(vals[order])
    explained = (vals[order] / vals.sum()).round(4).tolist()
    tick_to_cik = pd.Series(x.index, index=x["ticker"].to_numpy())
    ff12 = bt.static_groups.reindex(tick_to_cik.reindex(labels.index).to_numpy())["FF12"].to_numpy()
    ff12_names = dict(zip(sic_map(12)["industry"], sic_map(12)["name"]))
    comp = pd.read_parquet(ROOT / "data" / "interim" / "companies.parquet").set_index("ticker")["name"]
    pts = []
    for k, tk in enumerate(labels.index):
        sec = ff12_names.get(int(ff12[k]), "Other") if pd.notna(ff12[k]) else "Other"
        pts.append([tk, str(comp.get(tk, tk))[:40], sec, int(labels[tk])] + [rnd(v, 4) for v in coords[k]])
    return {"date": t.strftime("%Y-%m-%d"), "explained": explained, "cols": ["ticker", "name", "sector", "cluster", "pc1", "pc2", "pc3"],
            "points": pts}


def regime_surface() -> dict:
    main = pd.read_parquet(latest_run("full_main") / "returns.parquet").pivot(index="date", columns="book", values="excess_ret")
    th = pd.read_parquet(latest_run("posthoc_themes") / "returns.parquet").pivot(index="date", columns="book", values="excess_ret")
    books = {"Within-industry": main["W_FF49"], "Industry bets": main["B_FF49"], "Composite": main["C_FF49"]}
    for t in THEMES:
        books[f"Industry {t}"] = th[f"BT_{t}.FF49"]
    df = pd.DataFrame(books).sort_index()
    roll = df.rolling(24).mean() / df.rolling(24).std() * np.sqrt(12)
    roll = roll.dropna()
    return {"dates": [d.strftime("%Y-%m") for d in roll.index], "books": list(roll.columns),
            "z": [[rnd(v, 3) for v in roll[c]] for c in roll.columns]}


def main() -> None:
    bt, panel = runner._load_backtest()
    out = {"landscape": industry_landscape(bt, panel), "peer_map": peer_map(bt), "regime": regime_surface()}
    dst = ROOT / "docs" / "showcase_3d.json"
    dst.write_text(json.dumps(out, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"{dst.name}: {dst.stat().st_size / 1024:.0f} KB; frames {len(out['landscape']['frames'])}, "
          f"points {len(out['peer_map']['points'])}, PCA explained {out['peer_map']['explained']}")


if __name__ == "__main__":
    main()
