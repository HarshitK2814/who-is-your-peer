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

### EXP-005 — 2026-09-26 — Pre-registered test (2020–23) and recent (2024–26) evaluation
- Run after the "prereg: freeze" commit (b071a78), PREREG_HASH 3838565b5aca. One continuous backtest 2012-01 → 2026-07
  (175 months); dev/val months reproduce EXP-004 exactly. Constraints verified: |beta| ≤ 4e-6, gross ≤ 200% every month.
- H1: B_FF49 test Sharpe 0.68 [−0.31, 1.67]; Romano–Wolf p 0.080–0.109 across 4 schemes → claim not contradicted at 5%.
  Recent period reversal: B_FF49 −0.35. Deflated Sharpe of B_FF49 (17 trials) 0.32.
- H2: SIC3 − FF49 −0.23 (Holm p 0.14); RCLUST − FF49 +0.10 (Holm p 0.60) → fails.
- H3: CN_FF49 − C_FF49 +0.01 (p 0.96) → fails.
- Composite full-sample net Sharpe ≈ 0 (C_FF49 −0.04 [−0.56, 0.47]); gross ≈ 0.1; costs ≈ 0.6–0.9%/yr at 18–21% monthly turnover.
- Interpretation: industry-bet and within-industry components alternate by regime (low correlation 0.07–0.37); no design
  choice is statistically distinguishable in this free, survivorship-affected sample.
- Also found: report.py was briefly saved as cp1252 (Windows default) and failed silently; fixed, figures regenerated.
- Decision: report as is. Next: robustness runs (pre-registered), then CRSP replication if WRDS access becomes available.

### EXP-006 — 2026-09-26 — Pre-registered robustness variants (cost ×2, top-500 universe, no momentum)
- Full continuous runs 2012-01 → 2026-07; details in research/robustness.md.
- B_FF49 test Sharpe 0.63–0.70 in every variant (most stable result). Top-500 universe: H1 Romano–Wolf p = 0.004 (test),
  0.048 (full); H3 p = 0.04 (industry neutrality helped). Other variants: H1 not significant.
- Composite fragile: C_FF49 test Sharpe 0.15 (main) → −0.26 (top-500) → −0.27 (no momentum) → 0.01 (costs ×2).
- Interpretation: suggestive evidence that industry bets carried a premium among large caps in 2020–23, contrary to the
  filings' claim; not the primary test (3 variants), so it is reported as suggestive only.
- Decision: no further variants run (to avoid a forking-path search). Next step: CRSP replication.
- Note: the cost ×2 run stalled for ~1h while the machine was suspended; the results are unaffected (deterministic engine).

### EXP-007 — 2026-09-26 — POST-HOC: is the industry-bet premium industry momentum? (plan fixed before running)
- Plan and decision rule: research/posthoc_industry_momentum.md (written before running; after test results were seen).
- Result: not industry momentum in all 4 cells (INDMOM loadings −0.08…+0.04, |t| < 0.8; alpha unchanged or higher).
- Unplanned finding: B_FF49 realised market beta 0.19 (t 3.9, test) despite ex-ante beta 0 → ~2.3 of 6.1%/yr from leaked
  beta. Beta-hedged (trailing 36m, no look-ahead) test Sharpe 0.68 → 0.46. Top-500 universe: no leak (−0.01), hedged test
  Sharpe 0.68, full 0.39; CMA loading 0.23 (t 3.3).
- Bug found and fixed in the analysis script: period windows were offset by one month (returns indexed by earned month
  but sliced with signal-month bounds); fixed before interpreting.
- Decision: record as exploratory. Future version: Dimson/monthly beta + ex-post beta check, under a new pre-registration.

### EXP-008 — 2026-09-26 — POST-HOC: theme decomposition of the industry-bet premium (plan fixed before running)
- Plan: research/posthoc_theme_decomposition.md. Five BT_<theme>.FF49 books × {top1000, top500}, continuous 2012-01 → 2026-07.
- Plan flaw found: the attribution regression is near-mechanical (R² ~0.9, all t ≥ 3.9), so its t-criterion was
  uninformative. Kept the planned output; added return contributions as the informative measure (recorded, not hidden).
- Result: drivers = sentiment (most persistent; top500 full hedged Sharpe 0.60 [0.04, 1.15]) and management (2020–23);
  quality = consistent drag; valuation/growth industry components carry the leaked market beta (0.18 / 0.15).
- Multiplicity: 30 cells examined; no single cell is claimed as significant.
- Two escaping bugs in figure titles (sed/heredoc turned 
 into a real newline) found and fixed; no effect on numbers.
- Next (would need a new pre-registration): split sentiment into SUE vs momentum at industry level; Dimson/monthly betas.

### EXP-009 — 2026-09-26 — Interactive showcase page (docs/)
- `scripts/build_showcase_data.py` exports monthly net returns (6 runs) + the market factor; the page recomputes Sharpe,
  Lo (2002) CIs, drawdowns, realised beta and the trailing-36-month beta hedge in the browser (no hard-coded results in charts).
- Bugs found while checking the render: (1) duplicate `id="data"` made the page parse the wrong element; (2) the realised-beta
  calculation paired a period slice with the full-sample market series (showed 0.02 instead of 0.15). Both fixed; the JS beta
  was cross-checked against numpy on the same slice (0.151).
- Clarified in all copy: univariate realised beta 0.15 vs multi-factor loading 0.19 (t 3.9) in the test period.

### EXP-010 — 2026-09-26 — 3D views for the showcase (descriptive, no new hypotheses)
- `scripts/build_3d_data.py`: industry landscape (backtest universe, FF49 industry theme means at each signal date, the
  industry-bet book's net weight, next-month French 49-industry returns), peer map (Dec-2023 residual-return PCA, same
  clustering call as the backtest), regime surface (rolling 24-month Sharpe of 8 books).
- Facts shown on the page, computed from these data: industry composite-score vs next-month industry return rank corr 0.045
  (t 1.6) in 2020–23, ~0 in 2024–26, 0.006 full sample; 44% of the 50 return clusters have no sector with a 60% majority
  (utilities 96% pure); rolling-Sharpe correlation within vs industry bets −0.13.
- Bug fixed: NaN in the JSON (missing theme means) broke parsing; now written as null with allow_nan=False.
