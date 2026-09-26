# Experiment Log (append-only)

Every run that informs a decision is logged here, including failed ones. The run count feeds the
deflated Sharpe ratio. Format: hypothesis, method, data, period, benchmark, metric, result,
interpretation, decision.

### EXP-000 — 2026-09-26 — Project set-up and data-source decisions
- Decision: free data only (user requirement). SEC XBRL `companyfacts.zip` for fundamentals, `submissions.zip` for SIC,
  Yahoo (yfinance) for prices, Ken French library for factors/industries.
- Deviation from the original spec: Hoberg–Phillips TNIC peers dropped (free files keyed by Compustat gvkey; no free
  gvkey↔CIK link). Replaced by SIC-3 (TNIC-3's granularity benchmark) and return-correlation clusters.
- Known bias accepted: survivorship (current-listed tickers only). Mitigation: hypotheses are defined as differences
  between books on the same universe; universe restricted to the top 1000 non-financial stocks by market cap.
- Sample: signals 2012-01 → latest; development 2012–2016, validation 2017–2019, test 2020–2023 (locked), recent 2024+.
