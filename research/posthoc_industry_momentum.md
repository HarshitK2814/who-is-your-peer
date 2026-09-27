# Post-hoc analysis plan — Is the industry-bet premium just industry momentum?

**Status: written 2026-09-26 BEFORE running the analysis, but AFTER the test-period results were seen (EXP-005/006).
This is an explanatory (post-hoc) analysis, not a pre-registered test. It is labelled as such everywhere.**

## Question
The between-industry book B_FF49 was the most stable result (test Sharpe 0.63–0.70 across variants). Moskowitz &
Grinblatt (1999, JF) showed that industries with high past returns keep outperforming (industry momentum). Our
composite contains 12-1 stock momentum, and its industry mean is mechanically related to past industry returns.
**Is B_FF49's return explained by a standard industry-momentum factor?**

## Factor construction (fixed now)
Source: Ken French 49 industry portfolios, value-weighted monthly returns. These are CRSP-based, so the factor
itself is **survivorship-free**. At each month-end t, rank the 49 industries by past return, go long the top 15
and short the bottom 15, equal-weighted, and hold for month t+1.
* **INDMOM_6_0** (primary; the Moskowitz–Grinblatt specification): formation = months t−5 … t.
* **INDMOM_12_1** (secondary): formation = months t−11 … t−1.

## Tests
1. Time-series spanning: B_FF49 net excess return (earned in month t+1) on FF5 + UMD, then FF5 + UMD + INDMOM
   (each spec), Newey–West (6 lags). Periods: test 2020–23 and full 2012–26. Also for the no-momentum robustness
   run (B_FF49 built from a composite with no stock-level price momentum).
2. Exposure overlap: each month, correlate B_FF49's net portfolio weight per FF49 industry with the industries'
   past 6-month return rank (Spearman). Report the mean and t-stat across months.

## Decision rule (fixed now)
* **"Mostly industry momentum"** if adding INDMOM cuts B_FF49's alpha by > 50% AND the INDMOM loading has |t| ≥ 2.
* **"Not industry momentum"** if the alpha falls by < 25% or the INDMOM loading has |t| < 2.
* Otherwise **"partly"**.
Low power (48 test months) is acknowledged: this rule classifies point estimates. It is not a significance claim
about alpha.

---

## Results (run 2026-09-26 with `scripts/industry_momentum_test.py`)
Tables: `results/tables/posthoc_industry_momentum_{spanning,verdict,overlap}.csv`, `posthoc_beta_hedged.csv`.
Figure: `results/figures/posthoc_industry_momentum.png`. Returns indexed by the month they are earned
(test period = signals 2020-01…2023-12).

### 1. Not industry momentum (verdict under the fixed rule, all four run × period cells)
| Run / period | Alpha on FF5+UMD | + INDMOM_6_0 | INDMOM loading (t) | Verdict |
|---|---|---|---|---|
| main, test 2020–23 | 2.5%/yr (t 1.03) | 3.3%/yr | −0.07 (−0.56) | not industry momentum |
| main, full 2012–26 | −1.5%/yr | −1.6%/yr | +0.04 (0.58) | not industry momentum |
| no-stock-momentum composite, test | 2.3%/yr | 3.2%/yr | −0.08 (−0.72) | not industry momentum |
| no-stock-momentum composite, full | −1.3%/yr | −1.3%/yr | +0.02 (0.30) | not industry momentum |

The 12-1 industry-momentum specification gives the same answer (test loading −0.15, t −1.85: if anything
*negative*). Correlation of B_FF49 with INDMOM_6_0 over the full sample: 0.04. B_FF49's industry weights overlap only
slightly with past-winner industries (mean rank correlation 0.085 in the test period, t 3.9: statistically detectable,
economically small).

### 2. Unexpected finding: leaked market beta (not planned; reported as exploratory)
Although every month's portfolio had ex-ante beta 0 (constraint verified to 4e-6), B_FF49's **realised** beta to the
market was 0.19 (t 3.9) in the test period and 0.16 (t 3.9) over the full sample (multi-factor FF5+UMD loadings; the univariate beta in the table below is 0.15). Mkt-RF explains ≈ 2.3 of B_FF49's 6.1%/yr
test-period return. Likely cause: betas estimated from *daily* returns understate true (monthly) betas for less-synchronously
traded stocks (Scholes–Williams / Dimson problem), and aggregating to industry bets concentrates the error.
Composite books show small *negative* leaks (−0.04 to −0.07).

Hedging each book's beta with a trailing 36-month estimate (past data only):

| Book | Test Sharpe raw → beta-hedged | Full-sample raw → hedged | Univariate realised beta (test) |
|---|---|---|---|
| B_FF49, main universe | 0.68 → **0.46** [−0.52, 1.45] | 0.17 → 0.12 | 0.15 |
| B_FF49, top-500 universe | 0.70 → **0.68** [−0.31, 1.67] | 0.41 → **0.39** [−0.16, 0.95] | −0.01 |
| C_FF49 (composite), main | 0.15 → 0.21 | −0.04 → 0.12 | −0.04 |

Among the 500 largest stocks there is no leak, and the industry-bet premium survives. It loads on the investment factor
(CMA 0.23, t 3.3 in the test period) with FF5+UMD alpha 3%/yr (t 1.8).

### Interpretation
* The industry-bet result is **not a rediscovery of industry momentum**.
* In the broad universe, **about a third of it was leaked market beta**. That is a portfolio-construction flaw, not an
  industry premium, and it would also inflate any live "market-neutral" fund's returns in a bull market.
* Among large caps the premium is beta-clean and partly explained by conservative-investment industries (CMA).
  What remains is not significant with 48 months of data.
* **Methodological lesson:** a beta-neutrality constraint is only as good as the beta estimate. The next version should use a
  Dimson (lagged) or monthly-return beta and verify realised beta ex post. That requires a new pre-registration, because the
  test period has now been seen.
