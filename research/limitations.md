# Limitations

What this project does **not** establish, and why.

## Data (free sources only)
1. **Survivorship bias (largest issue).** Prices come from Yahoo for tickers that are listed *today*
   (SEC `company_tickers_exchange.json`). Companies that were acquired, went bankrupt or delisted before
   2026 are largely absent, so the historical universe is tilted toward winners. Consequences:
   * absolute Sharpe ratios of long/short books are **not** reliable estimates of real-world performance;
   * short books are especially affected (future losers that later delisted are missing from the short side);
   * our hypotheses compare books on the **same** universe, which removes the bias only to the extent
     it affects all books equally. It need not, e.g. if delisted firms cluster in particular industries.
   **Measured size of the gap** (`scripts/survivorship_diagnostic.py`, `results/tables/survivorship_coverage.csv`):
   among non-financial SEC filers with ≥ $1bn of assets, the share present in our priced universe,
   normalised to 2025 (when essentially all listed firms are present), is about **54% in 2012, 64% in 2016,
   78% in 2019, 82% in 2020, 93% in 2023 and 96% in 2024**. The bias is therefore severe in the development
   period, moderate in the test period (2020–2023) and small in the recent period.
   A CRSP-based replication (WRDS, often free via a university library) would fix this and is the
   single most valuable robustness check.
2. **SIC codes are current**, not historical. Firms that changed industry are misclassified in the past.
3. **Market capitalisation is approximate**: cover-page share counts × split-adjusted prices. Yahoo encodes
   some spin-offs as fractional splits, which briefly distorts shares and share issuance for those firms.
4. **XBRL tag coverage**: companies use different tags for the same concept. We use priority lists
   (`data/xbrl.py`), so some firms have missing characteristics, and a few tagging errors inevitably remain.
   Values are as first reported; restatements are ignored (correct for point-in-time, but noisier).
5. **No free borrow-fee or short-availability data**: a flat 25 bp/yr fee is assumed; hard-to-borrow
   names are only partly excluded by the $5 price and top-1000 size filters.
6. **Costs are modelled, not measured**: Abdi–Ranaldo spread estimates from daily OHLC, plus a
   square-root impact model with an assumed coefficient (Y = 0.5).

## Design
7. **Peer definitions**: TNIC (text-based) peers could not be used (Compustat identifiers). SIC-3 and
   return-correlation clusters are imperfect substitutes.
8. **Theme mapping is our reconstruction.** Vanguard's variables are not disclosed. In particular, QEG says
   its approach is "not technical analysis of stock price movements", so price momentum may not be part of
   its sentiment theme (we test the effect of removing it).
9. **Sample length**: 2012–2026 (~14 years) gives limited power; Sharpe differences below roughly 0.4–0.5
   are hard to detect. Non-rejections should be read as "not detectable with this sample", not "no effect".
10. **Monthly rebalancing** vs the disclosed "daily composite ranking".

## Interpretation
11. Nothing here measures or predicts the Vanguard fund's performance.
12. Paper-trading results (if any) are simulated and cover too few months to be evidence of performance.
