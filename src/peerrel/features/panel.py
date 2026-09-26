"""Monthly research panel: point-in-time fundamentals + market data, one row per (date, cik).

Timing convention (the bar the signal is computed on)
-----------------------------------------------------
* `date` is a calendar month-end t. All features use prices up to and including the last
  trading day <= t and fundamentals filed strictly before t.
* Trades are assumed at the close of the FIRST trading day after t ("t+1").
* `ret_fwd` is the total return from the t+1 close to the close of the first trading day
  after the next month-end. It is the *outcome* for the position formed at t and is the
  only forward-looking column; it is never used to build features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from peerrel.config import INTERIM, PROCESSED
from peerrel.features.fundamentals import point_in_time


def trading_calendar(px: pd.DataFrame) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(np.sort(px["date"].unique()))


def month_end_map(cal: pd.DatetimeIndex, start: str, end: str) -> pd.DataFrame:
    """For each calendar month-end t: last trading day <= t (signal bar) and first trading
    day > t (execution bar)."""
    mes = pd.date_range(start, end, freq="ME")
    last = cal[np.searchsorted(cal, mes, side="right") - 1]
    nxt_i = np.searchsorted(cal, mes, side="right")
    ok = nxt_i < len(cal)
    exe = pd.Series(pd.NaT, index=mes)
    exe[ok] = cal[nxt_i[ok]]
    return pd.DataFrame({"date": mes, "signal_day": last, "exec_day": exe.to_numpy()})


def abdi_ranaldo_spread(g: pd.DataFrame, window: int = 63) -> pd.Series:
    """Effective spread estimate from daily close/high/low (Abdi & Ranaldo 2017)."""
    c = np.log(g["close"])
    eta = (np.log(g["high"]) + np.log(g["low"])) / 2
    prod = (c - eta) * (c - eta.shift(-1))
    # prod at day d uses eta_{d+1}; shift so the rolling value at d only uses data <= d
    s2 = 4 * prod.shift(1).rolling(window, min_periods=40).mean()
    return np.sqrt(s2.clip(lower=0))


def market_features(px: pd.DataFrame, months: pd.DataFrame) -> pd.DataFrame:
    """Per (date, ticker) market features at the signal bar + forward return."""
    px = px.sort_values(["ticker", "date"]).copy()
    g = px.groupby("ticker", sort=False)
    px["vol_63d"] = g["ret"].transform(lambda s: s.rolling(63, min_periods=40).std())
    px["adv_63d"] = g["dollar_volume"].transform(lambda s: s.rolling(63, min_periods=40).median())
    px["spread"] = g[["close", "high", "low"]].apply(abdi_ranaldo_spread).reset_index(level=0, drop=True)
    px["n_obs"] = g.cumcount() + 1

    sig = px.merge(months[["date", "signal_day"]], left_on="date", right_on="signal_day", suffixes=("_d", ""))
    sig = sig.drop(columns=["date_d", "signal_day"])
    # month-end adjusted closes for momentum (t-1 and t-12 month-ends)
    wide = sig.pivot(index="date", columns="ticker", values="adj_close")
    mom = (wide.shift(1) / wide.shift(12) - 1).stack().rename("mom_12_1")
    # forward return: exec close at t -> exec close at t+1 month
    exe = px.merge(months[["date", "exec_day"]], left_on="date", right_on="exec_day", suffixes=("_d", ""))
    exe_w = exe.pivot(index="date", columns="ticker", values="adj_close")
    ret_fwd = (exe_w.shift(-1) / exe_w - 1).stack(future_stack=True).rename("ret_fwd")
    out = sig.set_index(["date", "ticker"])[["raw_close", "close", "adj_close", "split_factor_after",
                                             "vol_63d", "adv_63d", "spread", "n_obs"]]
    return out.join(mom).join(ret_fwd)


def split_factor_at(px: pd.DataFrame, ticker: pd.Series, when: pd.Series) -> pd.Series:
    """prod of split ratios strictly after `when` (last trading day <= when), per ticker."""
    q = pd.DataFrame({"ticker": ticker.to_numpy(), "when": pd.to_datetime(when).to_numpy(),
                      "i": np.arange(len(ticker))}).dropna().sort_values("when")
    ref = px[["ticker", "date", "split_factor_after"]].sort_values("date")
    got = pd.merge_asof(q, ref, left_on="when", right_on="date", by="ticker", direction="backward")
    return pd.Series(got["split_factor_after"].to_numpy(), index=got["i"].to_numpy()).reindex(range(len(ticker))).to_numpy()


def build_panel(period_chars: pd.DataFrame, px: pd.DataFrame, companies: pd.DataFrame,
                start: str = "2010-01-31", end: str | None = None) -> pd.DataFrame:
    cal = trading_calendar(px)
    end = end or str(cal[-1].date())
    months = month_end_map(cal, start, end)
    pit = point_in_time(period_chars, pd.DatetimeIndex(months["date"]), with_period=("shares_out",))
    pit = pit.reset_index().merge(companies[["cik", "ticker"]], on="cik", how="inner")

    mkt = market_features(px, months).reset_index()
    panel = pit.merge(mkt, on=["date", "ticker"], how="inner")

    # market cap: shares (as of their cover/period date) converted to today's split basis
    m = panel["m_shares_out"]
    share_date = pd.to_datetime(pd.DataFrame({"year": m // 12, "month": m % 12 + 1, "day": 1}),
                                errors="coerce") + pd.offsets.MonthEnd(0)
    f_s = split_factor_at(px, panel["ticker"], share_date)
    panel["shares_adj"] = panel["shares_out"] * f_s
    panel["mcap"] = panel["shares_adj"] * panel["close"]
    # second line of defence against share-count errors: daily dollar volume below 0.001% of
    # market cap (turnover < ~0.25%/yr) is implausible for an exchange-listed stock
    bad = (panel["adv_63d"] / panel["mcap"] < 1e-5) | (panel["mcap"] <= 0)
    panel.loc[bad, ["mcap", "shares_adj"]] = np.nan

    panel = panel.sort_values(["ticker", "date"])
    lag12 = panel.groupby("ticker")["shares_adj"].shift(12)
    same_gap = panel.groupby("ticker")["date"].diff(12) <= pd.Timedelta(days=370)
    panel["share_issuance_neg"] = -np.log(panel["shares_adj"] / lag12).where(same_gap)
    # valuation ratios (negative book equity -> not meaningful)
    panel["earnings_yield"] = panel["net_income_ttm"] / panel["mcap"]
    panel["book_to_market"] = (panel["equity"] / panel["mcap"]).where(panel["equity"] > 0)
    panel["cfo_yield"] = panel["cfo_ttm"] / panel["mcap"]
    panel["sales_yield"] = panel["revenue_ttm"] / panel["mcap"]
    panel = panel.replace([np.inf, -np.inf], np.nan)
    panel = panel.merge(companies[["cik", "sic", "exchange"]], on="cik", how="left")
    return panel.set_index(["date", "cik"]).sort_index()


if __name__ == "__main__":
    period = pd.read_parquet(INTERIM / "period_characteristics.parquet")
    px = pd.read_parquet(INTERIM / "daily_prices.parquet")
    comp = pd.read_parquet(INTERIM / "companies.parquet")
    panel = build_panel(period, px, comp)
    panel.to_parquet(PROCESSED / "panel.parquet")
    print(panel.shape)
