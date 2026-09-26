# Institutional Methodology — Vanguard Quantitative Equity Group (QEG)

Quotes below were extracted programmatically from the SEC filings on 2026-09-26 and are stored in
`research/sources/sec_excerpts.json`. Punctuation (em dashes, apostrophes) is restored from the HTML
entities. Everything outside quotation marks is our interpretation, labelled as such.

## Sources

| # | Filing | Registrant (CIK) | Accession | Filed | URL |
|---|---|---|---|---|---|
| S1 | Form N-CSR, FY ended 2020-12-31, Advisor's Report for **Vanguard Market Neutral Fund** (report dated 2021-01-19; J. P. Stetler, B. Guo, QEG) | Vanguard Montgomery Funds (1409957) | 0001104659-21-029823 | 2021-03-01 | https://www.sec.gov/Archives/edgar/data/1409957/000110465921029823/tm213573d6_ncsr.htm |
| S2 | Form 497K summary prospectus, **Vanguard Market Neutral Fund** Investor Shares | Vanguard Montgomery Funds (1409957) | 0001409957-26-000023 | 2026-04-28 | https://www.sec.gov/Archives/edgar/data/1409957/000140995726000023/f44872d1.htm |
| S3 | Form N-CSR, FY ended 2019-09-30, QEG section of **Vanguard Equity Income Fund** report | Vanguard Fenway Funds (826473) | 0001104659-19-068932 | 2019 | https://www.sec.gov/Archives/edgar/data/826473/000110465919068932/a19-22238_4ncsr.htm |

## Layer A — Explicitly disclosed (verbatim)

**S1 (2020 annual report, Market Neutral Fund):**
> "Our model uses five themes—growth, quality, management decisions, sentiment, and valuation—to evaluate companies and generate a composite expected stock return."

> "We seek to capitalize on investor biases by taking long positions in the stocks that our model ranks high and by shorting those that score the lowest."

> "We aim to keep your fund's sector exposures neutral, because our research has shown that sector bets do not add value over the long term."

> "…our approach to investing focuses on specific stock fundamentals and how companies rank relative to their industry peers."

**S2 (2026 summary prospectus, Market Neutral Fund):**
> "The Fund employs an active management approach, following a market neutral strategy, which the Fund defines as a strategy designed to produce a portfolio that is neutral with respect to general stock market risk (sometimes referred to as beta neutrality)."

> "The Fund, as a whole, does not seek to adhere to any other definition of market neutrality."

> "To implement the strategy, the advisor buys securities that it believes offer an appropriate balance between strong growth prospects and reasonable valuations relative to their industry peers and sells short securities that the advisor expects to be overvalued or have weak growth prospects, in amounts that it believes will achieve market neutrality."

> "The advisor does this by using a quantitative process… In addition, the advisor may emphasize specific industries, styles (growth/value), capitalization ranges, countries, or other factors."

> "…an absolute-return investment approach seeking performance that exceeds the returns of 3-month U.S. Treasury bills…"

**S3 (2019 annual report, QEG sleeve of Equity Income Fund):**
> "Our approach to investing focuses on fundamentals—not technical analysis of stock price movements. We use a strict quantitative approach to evaluate a stock's attractiveness based on five characteristics: high quality—healthy balance sheets and steady cash-flow generation; management decisions—sound investment policies that favor internal over external funding; consistent earnings growth—the ability to grow earnings year after year; strong market sentiment—market confirmation of our view; and reasonable valuation—we strive to avoid overpriced stocks. Using these five themes, we generate a daily composite stock ranking as we seek to capitalize on market inefficiencies. We then monitor our portfolio based on those rankings and adjust when appropriate to maximize expected returns while minimizing exposure to risks that our research indicates don't improve returns (such as industry selection and other risks relative to our benchmark)."

## Layer B — Our reconstruction (not disclosed; standard methods)

| Disclosed element | Our implementation | Why this choice |
|---|---|---|
| Five themes | 15 published characteristics mapped to themes (see `src/peerrel/signals/scores.py::THEMES`) | Each maps to a well-documented anomaly matching the disclosed wording, e.g. "internal over external funding" → net external financing (Bradshaw, Richardson & Sloan 2006) |
| "relative to their industry peers" | Rank-Gaussian transform of each characteristic within the peer group; undersized groups are pooled upward | Robust to outliers; the within-group mean of every score is 0 |
| "composite expected stock return" | Equal-weight average of theme z-scores, then α = IC · σ_idio · score (Grinold) | Equal weights avoid fitting theme weights (keeps the test about peers, not weights) |
| Long high / short low; beta neutrality | cvxpy optimiser: β'w = 0, gross ≤ 200%, 1% name cap, ADV cap, factor risk model, spread and square-root impact costs | Standard institutional construction |
| Sector neutrality (S1) | Variant `CN_*`: additional H'w = 0 per peer group | Directly tests S1 vs S2 |
| "market sentiment—market confirmation of our view" | SUE (earnings surprise) **and** 12-1 price momentum | **Ambiguity:** S3 says the approach is "not technical analysis of stock price movements", so QEG may not use price momentum. Our pre-specified ablation removes momentum to show its effect |
| "daily composite ranking" | Monthly rebalancing | Free data and compute; daily rebalancing is unnecessary for a slow composite and would inflate costs |

## Layer C — Our research extension

1. **Within/between decomposition** of the composite by peer group: the between component *is* the "sector bet" the filings say adds no value.
2. **Peer-definition comparison:** FF12, FF49, SIC-3 and return-correlation clusters. (The planned Hoberg–Phillips TNIC peers were dropped: the free files are keyed by Compustat gvkey, which cannot be linked to SEC CIKs without paid data. SIC-3 is the classification TNIC-3 is calibrated to match in granularity.)
3. **Neutrality variants** matching the S1 (sector-neutral) vs S2 (beta-only) wording.

## Unknown / proprietary (we make no claim about these)

Exact characteristic definitions, theme weights, the peer-group definition, the risk model, the optimiser, turnover limits, rebalance frequency, borrow handling, and why the 2026 prospectus wording differs from the 2020 report. We do **not** claim our results describe the fund's performance.
