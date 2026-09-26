# Data (all free)

Raw data is not committed. `python scripts/run.py download` recreates it. Every downloaded file
gets a `.manifest.json` with URL, retrieval time, size and sha256.

| Data | Source | Access | Used for |
|---|---|---|---|
| XBRL company facts (all SEC filers) | `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip` | Free; SEC requires a User-Agent with contact info (`SEC_USER_AGENT` in `.env`, never committed) | All fundamentals, with exact filing dates |
| Company submissions (SIC codes) | `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip` | Free | SIC industry codes |
| Ticker ↔ CIK ↔ exchange | `https://www.sec.gov/files/company_tickers_exchange.json` | Free | Universe, price matching |
| Daily prices, volume, splits, dividends | Yahoo Finance via `yfinance` | Free | Returns, market cap, liquidity, spreads |
| FF5 + momentum factors, daily and monthly; FF12/FF49 SIC maps | Ken French Data Library | Free | Beta, spanning regressions, risk-free rate, industries |

## Known limitations of free data (quantified in `research/limitations.md`)

1. **Survivorship bias.** The SEC ticker file and Yahoo cover *currently listed* companies. Firms that
   delisted before 2026 are mostly missing, so the universe at each past date is tilted toward survivors.
   Our hypotheses compare books built on the *same* universe (differences), which limits but does not
   remove the bias. The absolute Sharpe levels are biased upward.
2. **SIC codes are current, not point-in-time.**
3. **Market cap** = shares outstanding from the latest filing cover page × split-adjusted price
   (shares converted with Yahoo split ratios). Yahoo records some spin-offs as fractional splits,
   which briefly distorts shares and share issuance for those firms.
4. **XBRL coverage** starts 2009 (large filers) / 2011 (all filers), hence the 2012 sample start.
5. **No borrow-fee data**: a flat 25 bp/yr assumption.
