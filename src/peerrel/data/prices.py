"""Daily prices from Yahoo Finance (free, via yfinance) for the SEC primary-ticker universe.

Stored per batch (resumable) in long format. `close` is split-adjusted (not dividend-adjusted),
`adj_close` is split- and dividend-adjusted (total-return index), and `split` holds split
ratios on their ex-dates. Raw (as-traded) prices are reconstructed as
close_t * prod(splits after t).

Known data issues (see research/limitations.md): Yahoo omits most delisted tickers
(survivorship bias) and records some spin-offs as fractional "splits".
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from peerrel.config import INTERIM, RAW

PRICE_DIR = RAW / "prices"
FIELDS = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Adj Close": "adj_close",
          "Volume": "volume", "Stock Splits": "split", "Dividends": "dividend"}


def _download_batch(tickers: list[str], start: str) -> pd.DataFrame:
    raw = yf.download(tickers, start=start, auto_adjust=False, actions=True, progress=False,
                      threads=True, group_by="column")
    if raw.empty:
        return pd.DataFrame()
    long = raw.stack(level=1, future_stack=True).rename(columns=FIELDS).reset_index()
    long = long.rename(columns={"Date": "date", "Ticker": "ticker"})
    long = long.dropna(subset=["close"])
    return long[["date", "ticker"] + list(FIELDS.values())]


def download_all(tickers: list[str], start: str = "2008-01-01", batch: int = 100, pause: float = 3.0) -> None:
    PRICE_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(tickers), batch):
        out = PRICE_DIR / f"batch_{i // batch:04d}.parquet"
        if out.exists():
            continue
        chunk = tickers[i:i + batch]
        for attempt in range(4):
            try:
                df = _download_batch(chunk, start)
                break
            except Exception as e:  # yfinance raises assorted errors on throttling
                print(f"batch {i // batch} attempt {attempt + 1}: {e}", file=sys.stderr)
                time.sleep(30 * (attempt + 1))
        else:
            continue
        df.to_parquet(out, index=False)
        print(f"batch {i // batch:04d}: {df['ticker'].nunique() if len(df) else 0}/{len(chunk)} tickers", flush=True)
        time.sleep(pause)


def load_prices() -> pd.DataFrame:
    parts = [pd.read_parquet(p) for p in sorted(PRICE_DIR.glob("batch_*.parquet"))]
    px = pd.concat(parts, ignore_index=True)
    px["date"] = pd.to_datetime(px["date"]).dt.tz_localize(None)
    px["split"] = px["split"].replace(0.0, np.nan)
    return px.sort_values(["ticker", "date"]).reset_index(drop=True)


def future_split_factor(px: pd.DataFrame) -> pd.Series:
    """prod of split ratios strictly after each date, per ticker (so raw = close * factor)."""
    s = np.log(px["split"].fillna(1.0))
    total = s.groupby(px["ticker"]).transform("sum")
    upto = s.groupby(px["ticker"]).cumsum()
    return np.exp(total - upto)


def build_daily_panel() -> Path:
    px = load_prices()
    px["split_factor_after"] = future_split_factor(px)
    px["raw_close"] = px["close"] * px["split_factor_after"]
    px["ret"] = px.groupby("ticker")["adj_close"].pct_change(fill_method=None)
    px["dollar_volume"] = px["close"] * px["volume"]
    out = INTERIM / "daily_prices.parquet"
    px.to_parquet(out, index=False)
    print(f"daily panel: {px['ticker'].nunique():,} tickers, {len(px):,} rows -> {out}")
    return out


if __name__ == "__main__":
    comp = pd.read_parquet(INTERIM / "companies.parquet")
    download_all(comp["ticker"].tolist())
    build_daily_panel()
