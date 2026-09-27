# Results

All returns are monthly **net excess returns over the 1-month T-bill**, after modelled spread (Abdi–Ranaldo) and
square-root impact costs, a 25 bp/yr borrow fee, at a **$100M NAV capacity assumption**, 200% gross,
beta-neutral. Sharpe ratios are annualised with 95% CIs (Lo 2002). One continuous backtest, 2012-01 → 2026-07
signal months (175 monthly rebalances; ~430–570 positions per book per month). Run:
`results/runs/20260926-1702_full_main` (reproduces the development/validation run exactly: max difference 0.0).
Constraint check: |ex-ante beta| ≤ 4e-6 and gross ≤ 200% in every month.

**Survivorship caveat:** the universe covers ~54% (2012) → 82% (2020) → 93% (2023) of the large firms listed at the
time (EXP-003). Absolute levels are upward-biased; comparisons between books are the object of the study.

## Pre-registered hypotheses — test period 2020-01 → 2023-12 (48 months)

| Hypothesis | Result | Frozen decision rule | Verdict |
|---|---|---|---|
| **H1** industry-bet (between-peer) books earn a positive premium | Sharpe B_FF12 0.61, **B_FF49 0.68 [−0.31, 1.67]**, B_SIC3 0.61, B_RCLUST 0.71; Romano–Wolf p = 0.109 / **0.085** / 0.109 / 0.080 | contradicted if any p_RW < 0.05 | **Not contradicted** (claim "sector bets do not add value" survives at 5%, but point estimates are positive) |
| **H2** peer definition matters | SIC3 − FF49 = −0.23 [−0.48, 0.02], Holm p = 0.14; RCLUST − FF49 = +0.10 [−0.27, 0.47], Holm p = 0.60 | fails if both Holm p ≥ 0.05 | **Fails** (no detectable difference) |
| **H3** explicit industry neutrality changes performance | CN_FF49 − C_FF49 = +0.01 [−0.25, 0.27], p = 0.96 | fails if p ≥ 0.05 | **Fails** |

Deflated Sharpe ratio of B_FF49 in the test period (17 books as trials): **0.32**, i.e. the best "industry-bet" result is
well within what the multiplicity of books could produce by chance.

## Book performance (net)

| Book | Test 2020–23 Sharpe [95% CI] | Ann. return | Max DD | Recent 2024–26 Sharpe | Full 2012–26 Sharpe [95% CI] |
|---|---|---|---|---|---|
| C_ALL (no peers) | 0.39 [−0.59, 1.38] | 3.3% | −15.6% | 0.24 | 0.02 [−0.50, 0.53] |
| C_FF49 (peer-relative) | 0.15 [−0.84, 1.13] | 1.0% | −14.6% | 0.83 | −0.04 [−0.56, 0.47] |
| CN_FF49 (+ industry-neutral) | 0.15 [−0.83, 1.13] | 1.0% | −14.0% | 0.51 | −0.15 [−0.67, 0.36] |
| W_FF49 (within component) | −0.02 [−1.00, 0.96] | −0.1% | −16.7% | 0.61 | −0.03 [−0.55, 0.48] |
| B_FF49 (between component) | 0.68 [−0.31, 1.67] | 6.1% | −6.9% | −0.35 | 0.17 [−0.34, 0.69] |
| C_SIC3 | −0.08 [−1.06, 0.90] | −0.5% | −15.1% | 1.15 | −0.10 [−0.61, 0.42] |
| C_RCLUST | 0.24 [−0.74, 1.23] | 1.6% | −13.1% | 0.54 | −0.02 [−0.53, 0.49] |

Turnover ≈ 18–21% one-way per month; modelled costs ≈ 0.6–0.9% per year; gross (pre-cost, pre-borrow) full-sample
Sharpe of the composites is only 0.08–0.15. Full tables: `results/tables/book_summary_{development,validation,test,recent,full}.csv`,
`hypotheses_*.csv`.

## What we learned

1. **The five-theme composite, as reconstructed from public definitions, has no reliable net alpha in 2012–2026**
   in this universe (full-sample Sharpe ≈ 0, FF5+UMD spanning alpha insignificant). It loads on HML, RMW and UMD and
   suffered in the 2017–2019 value drawdown (validation Sharpe ≈ −1.4 to −1.7).
2. **The filings' claim cannot be rejected, but the evidence is regime-dependent, not "no value".** The industry-bet
   component was the best-performing book in 2020–2023 (Sharpe ≈ 0.7, max drawdown only −7%) and the worst in
   2024–2026 (−0.35). Its correlation with the within-industry component is low (0.07–0.37 by period), so it is a
   genuinely different bet with a large but unstable premium. A 48-month test cannot distinguish that from zero.
3. **Peer definition and explicit industry neutrality made no detectable difference.** Once characteristics are ranked
   within peers, adding an industry-neutrality constraint changes almost nothing (H3 difference 0.01), consistent with
   the peer-relative ranking already doing most of the neutralising.
4. **Unusual result:** within-peer and between-peer components took turns: between > within in 2020–23 (+0.70 Sharpe gap),
   within > between in 2024–26 (+0.96 gap). A fixed choice of "neutralise industries" vs "allow industry bets" would
   have looked right or wrong depending on which four years one checked. That is a concrete argument for testing such
   design claims over long samples (ideally CRSP 1990+), not a license to time them.

## Robustness (pre-registered; reported regardless of outcome)
See `research/robustness.md`. The industry-bet book's test Sharpe is 0.63–0.70 in all variants. In the **top-500 universe
it is significant** (Romano–Wolf p = 0.004; full sample 0.048) and industry neutrality helps (H3 p = 0.04). That is
suggestive evidence against the filings' claim among large caps (a robustness arm, not the primary test). The composite
itself is fragile (test Sharpe from −0.27 to 0.15 across variants).

## Post-hoc: is it industry momentum? (exploratory; `posthoc_industry_momentum.md`)
**No.** Controlling for a Moskowitz–Grinblatt industry-momentum factor leaves the industry-bet alpha unchanged (loading
−0.07, t −0.56). But the analysis revealed that the "beta-neutral" industry-bet book had a **realised market beta of 0.19
(t 3.9)**. Daily-return betas understated true betas, so about a third of its test return (2.3 of 6.1%/yr) was leaked
market exposure in a rising market. Hedging that with past data only cuts its test Sharpe from 0.68 to 0.46. Among the 500
largest stocks there is no leak and the premium survives (hedged Sharpe 0.68 test, 0.39 full), loading on CMA.

## Post-hoc: which theme drives it? (exploratory; `posthoc_theme_decomposition.md`)
The industry-bet premium comes mainly from the **sentiment** theme's industry component (earnings surprises and momentum
averaged by industry; the most persistent driver, and barely correlated with the industry-momentum factor) and, in 2020–23,
from **management decisions** (industries funding themselves internally). The **quality** industry component was a
consistent drag. The leaked market beta sits mainly in the **valuation** industry component. None of the 30 cells examined
post hoc is claimed as significant after multiplicity.

## Not established
Anything about the Vanguard fund's own performance; any result on a survivorship-free universe; statistical significance
for any hypothesis. See `limitations.md`.
