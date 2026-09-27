# Post-hoc analysis plan — Which theme drives the industry-bet premium?

**Status: written 2026-09-26 BEFORE running, AFTER test results were seen. Exploratory (post-hoc), not pre-registered.**

## Question
The between-industry book B_FF49 (industry mean of the five-theme composite) was the most stable result, and among the
500 largest stocks it survives beta hedging. The composite is an equal-weight average of five themes, so its industry
mean is the average of five theme-level industry means. **Which themes' industry components carry the return?**

## Method (fixed now)
* Five new books, BT_<theme>.FF49: the FF49-industry mean of one raw theme score, z-scored, traded exactly like B_FF49
  (same optimiser, beta-neutral, costs, borrow, λ = 8, $100M). Themes: quality, management, growth, sentiment, valuation.
* Two universes: main (top 1000) and top 500. One continuous backtest 2012-01 → 2026-07 each.
* Report per theme book: net Sharpe (test 2020–23, full 2012–26, recent 2024–26), beta-hedged Sharpe (trailing 36-month
  beta, past data only), realised beta, and correlation with B_FF49.
* Attribution: regress B_FF49 on the five theme-book returns (full sample). The largest positive, significant
  coefficients identify the drivers.

## How results will be read
* A theme is a **driver** if its between-book has a beta-hedged test Sharpe ≥ 0.5 AND a positive attribution coefficient
  with t ≥ 2 (full sample).
* If no theme qualifies, the premium is **diffuse** (it comes from combining themes, not from any single one).
* No new themes, peer schemes or parameters will be tried after seeing these results.

---

## Results (run 2026-09-26, `scripts/theme_decomposition.py`)
Tables: `results/tables/posthoc_theme_{between_books,attribution,verdict,return_contributions}.csv`.
Figure: `results/figures/posthoc_theme_decomposition.png`.

### Note on the reading rule (a flaw in the plan, recorded rather than silently changed)
The attribution regression is near-mechanical: B_FF49 is essentially the average of the five theme components
(R² 0.87–0.95), so **every** coefficient is positive with t ≥ 3.9. The "t ≥ 2" condition therefore discriminates
nothing, and the rule reduces to "beta-hedged test Sharpe ≥ 0.5". The rule's output is kept as planned (drivers:
**management** and **sentiment** in both universes). We add each theme's **return contribution** (coefficient × theme-book
mean return) as the more informative measure.

### Findings
| Theme's industry component | Beta-hedged Sharpe: test (top1000 / top500) | Full sample (top1000 / top500) | Return contribution, test (top1000 / top500) | Read |
|---|---|---|---|---|
| **Sentiment** | 1.11 / 0.70 | 0.26 / **0.60 [0.04, 1.15]** | +2.6 / +1.6 %/yr | Most persistent driver; also strongest in 2024–26 (1.08 / 1.52). Correlation with the industry-momentum factor only 0.01–0.24 |
| **Management** (external financing) | 0.92 / 0.78 | 0.24 / 0.15 | +2.0 / +1.5 | Strong in 2020–23, reverses in 2024–26; consistent with the CMA loading |
| Valuation | 0.12 / 0.07 | −0.05 / 0.09 | +1.9 / +1.2 | Raw contribution is mostly **leaked market beta** (realised beta 0.18 in the test period, top1000) |
| Growth | −0.22 / 0.42 | −0.21 / 0.04 | +0.1 / +0.5 | Also carries beta (0.15, top1000) |
| **Quality** | −0.11 / −0.30 | −0.17 / −0.53 | −0.3 / −0.8 | Consistent **drag**: tilting toward high-quality industries lost money (2024–26: −1.0 / −1.7) |

### Interpretation (exploratory)
1. The industry-bet premium is **not diffuse**. It comes mainly from the industry-level **sentiment** theme (earnings
   surprises plus price momentum averaged by industry) and, in 2020–23, from industry-level **management decisions**
   (industries whose firms fund themselves internally).
2. Because the sentiment industry book barely correlates with the Moskowitz–Grinblatt industry-momentum factor,
   the earnings-surprise component, i.e. slow diffusion of industry-wide earnings news (cf. Hou 2007, industry
   information diffusion), is the more likely channel. **Not tested here:** splitting sentiment into its two parts would be a
   new analysis and needs its own plan.
3. The **beta leak** found in step 1 sits mainly in the **valuation** (and growth) industry components: cheap industries
   carried hidden market beta.
4. The only interval excluding zero (sentiment, top 500, full sample, 0.60 [0.04, 1.15]) is one of 30 theme × universe ×
   period cells examined post hoc. After multiplicity it is **not** significant evidence. It is a lead for a
   pre-registered follow-up.
