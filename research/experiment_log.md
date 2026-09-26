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

### EXP-001 — 2026-09-26 — Data-quality fixes found during the panel build
- Found: cover-page `dei:EntityCommonStockSharesOutstanding` mis-scaled ×1000 in some 2019–2024 filings
  (e.g. CIK 1108426, 887359, 719413), creating trillion-dollar market caps.
- Fix: correct only ratios in [500, 2000] (or inverse) vs the balance-sheet share count / previous corrected value
  (genuine splits untouched; unit test added). Second guard: market cap set missing when 63-day median dollar
  volume < 0.001% of market cap.
- Found: return clusters unavailable in the first year (need a prior December); fixed with a warm-up fit.
- Found: 'between' signal degenerates to floating-point noise when all stocks share one group; fixed with a
  zero-variance guard.
- Decision: keep all fixes; none uses returns.

### EXP-002 — 2026-09-26 — Risk-aversion calibration (development months only, ex-ante risk only)
- Hypothesis: n/a (engineering). Book C_FF49, every 4th development month (15 months), λ ∈ {2,…,128}.
- Result: median ex-ante vol 3.7% (λ=2) … 0.9% (λ=128); the 200% gross cap binds up to λ=32.
- Interpretation: the spec's 6% vol target is infeasible at 200% gross for a diversified beta-neutral book.
- Decision: target 3% → λ = 8 (median ex-ante vol 3.1%). Frozen in configs/backtest.yaml.

### EXP-003 — 2026-09-26 — Survivorship coverage diagnostic
- Method: large (≥ $1bn assets) non-financial SEC filers vs our priced universe, per year-end.
- Result (normalised to 2025): 54% (2012) → 82% (2020) → 93% (2023) → 96% (2024).
- Decision: report absolute Sharpe ratios as upward-biased, especially 2012–2019. Emphasise differences between
  books; the test period is materially less affected than development.

### EXP-004 — 2026-09-26 — Development (2012–16) and validation (2017–19) backtest, all 17 books
- Method: continuous monthly backtest 2012-01 → 2019-12, frozen config (λ=8), net of spread + impact + 25 bp borrow, $100M NAV.
- Development (60 months), net Sharpe [95% CI]: C_ALL 0.22 [−0.66, 1.09]; C_FF49 0.31 [−0.57, 1.19];
  CN_FF49 0.15 [−0.73, 1.02]; W_FF49 0.34 [−0.54, 1.22]; B_FF49 −0.09 [−0.96, 0.79]. Turnover ≈ 16%/month one-way, costs ≈ 0.5%/yr.
- Validation (36 months): C_ALL −1.37 [−2.55, −0.20]; C_FF49 −1.70 [−2.90, −0.51]; CN_FF49 −1.72; W_FF49 −1.38;
  B_FF49 +0.31 [−0.83, 1.44]. Max drawdown of C_FF49 −22%.
- Diagnosis (not a bug): composite rank IC ≈ 0.00 in validation; the valuation theme IC −0.045 (t −1.9); FF5+UMD regression
  shows HML loading ≈ 0.25–0.5 — 2017–2019 was a deep value drawdown. Gross losses exceed what a zero-IC signal implies,
  so the optimised book also has an unfavourable residual (spanning alpha ≈ −4.7%/yr, t −2.0).
- Also found: the first ~3 months of any run ramp up from cash (impact-cost penalty). Decision: the test evaluation will slice
  one continuous backtest from 2012 (positions carried over), not restart in 2020.
- Decision: **no change to signals, weights or parameters** in response to the poor validation results (changing them now
  would be fitting to validation). Hypotheses H1–H3 frozen as drafted. Validation already shows the between-industry books
  (B_*) did *not* lose in 2017–19 while the within/peer books did — H1 is a live question for the test period.
