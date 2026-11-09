"""Build and cache the style-model inputs (month-end exposures, daily factor returns, residuals)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from peerrel.backtest import BacktestConfig, eligible
from peerrel.v2 import stylemodel as sm

STYLE_UNIVERSE = 1500


def month_exposures(panel: pd.DataFrame, daily_ret: pd.DataFrame, mkt: pd.Series, months: pd.DataFrame,
                    ind49: pd.Series, cfg: BacktestConfig, n_universe: int = STYLE_UNIVERSE
                    ) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    """Per month-end t (data <= signal bar only): universe = eligible, top n_universe by mcap.
    Returns a long table (date, ticker, STYLES, ind) and the dict used by stylemodel.fit_history."""
    months = months.set_index("date") if "date" in months.columns else months
    long, expo = [], {}
    avail = panel.index.get_level_values("date").unique()
    for t in months.index:
        if t not in avail:
            continue
        x = eligible(panel.loc[t], cfg).nlargest(n_universe, "mcap")
        if len(x) < 200:
            continue
        sig_day = months.loc[t, "signal_day"]
        win = daily_ret.loc[:sig_day].iloc[-252:].reindex(columns=x["ticker"])
        beta = sm.market_beta(win, mkt)
        beta.index = x.index
        S = sm.style_exposures(x, beta)
        ind = ind49.reindex(x.index)
        D = sm.industry_dummies(ind.astype(float))
        E = pd.concat([D, S], axis=1)[sm.FACTORS]
        E.index = x["ticker"].to_numpy()
        E["w"] = np.sqrt(x["mcap"].to_numpy(dtype=float))
        expo[t] = E
        row = S.copy()
        row.insert(0, "ind", ind.to_numpy())
        row["ticker"] = x["ticker"].to_numpy()
        row["date"] = t
        long.append(row.reset_index(drop=True))
    return pd.concat(long, ignore_index=True), expo


def load_or_build(root: Path, panel, daily_ret, mkt, months, ind49, cfg, force: bool = False):
    p = root / "data" / "processed"
    fe, ff, fr = p / "style_expo.parquet", p / "style_fret.parquet", p / "style_resid.parquet"
    if not force and fe.exists() and ff.exists() and fr.exists():
        return pd.read_parquet(fe), sm.StyleHistory(pd.read_parquet(ff), pd.read_parquet(fr))
    table, expo = month_exposures(panel, daily_ret, mkt, months, ind49, cfg)
    hist = sm.fit_history(expo, months.set_index("date")["signal_day"] if "date" in months.columns else months["signal_day"],
                          daily_ret)
    table.to_parquet(fe)
    hist.fret.to_parquet(ff)
    hist.resid.to_parquet(fr)
    return table, hist
