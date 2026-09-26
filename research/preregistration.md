# Pre-registration — P1 "Who Is Your Peer?"

**Status: FROZEN (commit "prereg: freeze", 2026-09-26), written after development/validation results
(EXP-004) and before any test-period computation. The test
period (2020-01 → 2023-12) and recent period (2024-01 →) can only be run after that commit, with
`PREREG_HASH` set to this file's hash (enforced by `qcore.splits.guard`).**

## Data and universe
Free data only (see `data/README.md`). Monthly signals at calendar month-ends. Universe: top 1000
non-financial (SIC ∉ 6000–6999) NYSE/Nasdaq stocks by market cap with raw price ≥ $5, ≥ 252 trading
days of history and ≥ 3 of 5 themes available. Trades at the t+1 close; holding period to the next
month's t+1 close.

## Books (all beta-neutral, same optimiser, costs, borrow, $100M NAV)
| Book | Signal | Extra constraint |
|---|---|---|
| C_ALL | composite, characteristics ranked across the full universe | — |
| C_s | composite, characteristics ranked within peer scheme s | — |
| CN_s | as C_s | industry-neutral in scheme s |
| W_s | within-peer part of the C_ALL composite (S − peer mean) | — |
| B_s | between-peer part (peer mean of the C_ALL composite) | — |
s ∈ {FF12, FF49, SIC3, RCLUST}

## Hypotheses
**H1 (primary; the filings' claim).** The between-peer (industry-bet) component earns no positive
premium. Test: one-sided Romano–Wolf stepdown (stationary bootstrap, mean block 6, 5,000 draws) on the
mean net excess return of B_FF12, B_FF49, B_SIC3, B_RCLUST.
*Outcome rule:* the filings' claim is **contradicted** if any B_s has p_RW < 0.05. It is **consistent**
otherwise. We also report the Sharpe and 95% CI of each B_s.

**H2.** Peer definition matters: Sharpe(C_SIC3) − Sharpe(C_FF49) ≠ 0 and Sharpe(C_RCLUST) − Sharpe(C_FF49) ≠ 0.
Test: HAC delta-method Sharpe-difference test (Newey–West, 6 lags), Holm-adjusted over the two comparisons.
*Fails* if both Holm-adjusted p ≥ 0.05.

**H3.** Explicit industry neutrality changes performance: Sharpe(CN_FF49) − Sharpe(C_FF49) ≠ 0 (same test).
*Fails* if p ≥ 0.05.

## Evaluation run
One continuous backtest 2012-01 → latest (positions carried across period boundaries), sliced to the test
period for evaluation. Development/validation months are identical to EXP-004 by construction (deterministic).

## Primary metric and period
Net-of-cost monthly excess return over the 1-month T-bill (Ken French RF). Primary evaluation: the
**test period 2020-01 → 2023-12** (48 months). Secondary: the recent period 2024-01 → latest, reported
separately. Also reported: the pooled 2012–latest sample (clearly labelled as partly in-sample).

## Frozen parameters
`configs/backtest.yaml` as of the freeze commit (IC 0.03, borrow 25 bp, cost multiplier 1, impact Y = 0.5,
NAV $100M, gross 200%, name cap 1%, ADV cap 5%, universe 1000, 50 return clusters, risk aversion λ = 8 from
development-only calibration, EXP-002).

## Robustness (reported regardless of outcome; not used to choose anything)
Cost multiplier 2.0; universe 500; composite without price momentum (tests the "not technical analysis" ambiguity).

## Power caveat (stated ex ante)
48 test months cannot detect Sharpe differences much below ~0.8. Non-rejections will be reported as
"not detectable in this sample".
