# Pre-registration v2: Who Is Your Peer? (P1)
Frozen 2026-11-09, before any v2 hypothesis statistic was computed. v1 pre-registration, results and runs are unchanged.
Branch note: the repo branch is `master`.

## Evidence ranking
1. Forward paper tracking from the 2026-11 signal month (only unseen data). 2. Design-period statistics on 2012-01..2019-12
(v1 development + validation; 96 monthly signals). 3. 2020-01..2026-07: **seen period (v1 reported it)**, descriptive only.
The design period is where v2 choices could be made; every v2 number below was fixed here, not tuned. Design-period
results are therefore not out-of-sample for the *v1 signal*, and 96 months is thin: every Sharpe carries a 95% CI
(stationary bootstrap, mean block 6) and its month count.

Timing: the composite is computed at month-end signal bar t (prices <= t, filings filed before t); trades fill at the
t+1 close; holding to the next month's t+1 close (`ret_fwd`). Style-model factor returns and specific variances use
only days <= t, and exposures lagged to the previous month-end.

## Books (all beta-neutral, $100M NAV, v1 costs: half-spread + square-root impact, 20 bp forced exits)
Base signal: C_FF49 composite (v1 primary). All five share the **v2 borrow model**: tiered fee on shorts, applied in the
optimiser objective and the accounting, 25/50/150 bp/yr for universe market-cap rank 1-500 / 501-800 / 801-1000
(assumption; no free stock-loan data; D'Avolio 2002 puts general collateral near 17 bp).
| Book | Definition |
|---|---|
| V0_FF49 | C_FF49 + v2 borrow model (the v2 baseline; v1 C_FF49 used flat 25 bp) |
| SN_FF49 | V0 + style neutral: each of 8 style exposures of the book within +-0.05 |
| SIN_FF49 | SN + FF49 industry neutral (exact) |
| T_FF49 | V0 + one-way turnover cap 10% of NAV per month (soft fallback to uncapped when infeasible; count reported) |
| TSIN_FF49 | SIN + turnover cap |
Styles: size (log mcap), value (book-to-market), momentum (mom_12_1), profitability (gp_to_assets), leverage, investment
(asset_growth_neg), volatility (63-day), beta (trailing 252-day market beta); standardised within the month's universe.
Style model: FF49 industry dummies + 8 styles, WLS (weights sqrt(mcap)), daily cross-sections over the trailing 252 days
with exposures from the latest month-end before each day, factor covariance Ledoit-Wolf, specific variance blended 0.7/0.3
with the cross-sectional median. A parity check must reproduce v1 C_FF49 returns when all v2 options are off.

## Primary hypotheses (design period 2012-01..2019-12)
- **H1 (neutral alpha).** The industry+style-neutral composite earns a positive net excess return. Test: one-sided
  Romano-Wolf stepdown (stationary bootstrap, block 6, 5,000 draws, seed 0) on the mean net excess return of
  {SN_FF49, SIN_FF49, TSIN_FF49}. Supported if SIN_FF49 has p_RW < 0.05. Reported either way, with Sharpe and 95% CI.
  Expectation stated ex ante: v1's composite had Sharpe about 0 net, so a null is the likely outcome.
- **H2 (risk model).** The fundamental style model forecasts monthly portfolio risk better than v1's PCA-10 model.
  Test portfolios (not optimised under either model): for each of the 15 characteristics, the equal-weight top-decile minus
  bottom-decile portfolio in the monthly universe, long and short legs each $1. Loss: QLIKE = log(s2) + r^2/s2 with
  r the realised next-month return (`ret_fwd`) and s2 the model's monthly variance forecast. Statistic: the
  month-average over portfolios of QLIKE(PCA) minus QLIKE(style), 2013-01..2019-12 (the style model needs 2012 history).
  Supported if the mean is positive and its 95% stationary-bootstrap CI (block 6) excludes 0. Also reported: bias
  statistic std(r/s) per model (1 is perfect) and the variance split of each v2 book into industry, style and specific.
- **H3 (turnover cap).** T_FF49 vs V0_FF49: Sharpe difference tested with the HAC (Newey-West, 6 lags) delta-method test
  of v1. Supported if the difference is positive and p < 0.05 two-sided. Reported with turnover and cost, so a cap that
  lowers cost but not Sharpe is visible.
- **H4 (overfitting audit of v1).** Over the 17 v1 books on 2012-01..2019-12: PBO (CSCV, 8 blocks of 12 months) < 0.5
  and deflated Sharpe of v1 C_FF49 (n_trials = 17) > 0.90. Sensitivity (descriptive): n_trials = 17 + 5 new books, and
  n_trials counting the 3 robustness runs of v1 (68). Romano-Wolf of v1 H1 is kept and extended in H1 to the new books.

## Descriptive (no hypothesis)
- D1 borrow: flat fee sweep 25/50/100/200/400 bp and the tiered model on V0; breakeven fee (mean net excess = 0);
  fixed weights re-priced. Tiers are assumptions, not data.
- D2 capacity: per-trade ADV participation (|dw| x NAV / ADV) quantiles, share of trades above 5% and 20% of ADV,
  and NAV sweep $25M/$100M/$250M/$1B/$5B re-costing the $100M weights (an upper bound on net return because weights are not
  re-optimised). Capacity = largest NAV whose net Sharpe is within 0.10 of the $100M value.
- D3 v1 family: seen-period version of every table (2020-01..2026-07) labelled `seen period (v1 reported it)`.
- D4 skfolio MeanRisk vs cvxpy cross-check on sampled months (weight correlation, objective gap).

## Exploratory (labelled exploratory, never headline)
- E1 SHAP: HistGradientBoosting on the 15 within-FF49 rank-gaussian characteristics -> cross-sectional rank of next-month
  return, trained 2012-01..2016-10, evaluated 2017-01..2019-12 (rank IC vs the equal-weight composite IC, bootstrap CI);
  mean |SHAP| by theme.

## Not done (stated now)
Hoberg-Phillips text peers rebuilt from 10-K Item 1 (see evidence_v2.md). No external or CRSP replication.

## Forward test
From the 2026-11 signal month, `scripts/v2/forward.py` logs month-end target weights and realised returns of V0_FF49,
SIN_FF49 and v1 C_FF49. Earliest read: 12 months of outcomes (2027-12). Report Sharpe with CI and month count.

## What would change our conclusions
A bug found after freezing is fixed, logged in experiment_log_v2.md, and both numbers reported.
