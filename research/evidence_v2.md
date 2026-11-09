# P1 evidence for v2 (peer-relative equity)

Checked 2026-11-09 by web search (result pages and snippets read; full papers NOT read unless stated). Fund filings are descriptions of the manager, not performance claims.

## Sources

| # | Source | Type | Finding used | Link |
|---|---|---|---|---|
| S1 | Hoberg and Phillips (2016), "Text-Based Network Industries and Endogenous Product Differentiation", JPE 124(5) | Academic | TNIC peers come from 10-K product descriptions (50,673 filings), are time-varying and firm-specific, and explain managers' named rivals and firm characteristics better than SIC/NAICS. | [NBER w15991](https://www.nber.org/papers/w15991) |
| S2 | MSCI Barra methodology (USE4 coverage, MSCI factor-return note, unofficial handbook copy) | Vendor | Fundamental factor model: factor returns by cross-sectional regression of asset returns on industry and style exposures; factor covariance from the factor-return history; return = common + specific. USE4 industries are pure-industry (net of style) factors. Handbook text read only through an unofficial Scribd copy. | [MSCI brochure](https://www.msci.com/downloads/web/msci-com/data-and-analytics/factor-investing/equity-factor-models/MSCI-Equity-Factor-Models_Brochure.pdf), [MSCI FaCS](https://www.msci.com/www/research-paper/introducing-msci-facs/0830612157) |
| S3 | Kakushadze and Yu, "Custom v. Standardized Risk Models" | Academic | Risk factors inside an optimiser add noise to holdings and trades, raising trading costs; custom models can be built from free data. | [arXiv 1409.2575](https://arxiv.org/pdf/1409.2575) |
| S4 | Ehsani, Harvey and Li, "Is Sector Neutrality in Factor Investing a Mistake?" (Duke) | Academic | Sector neutralisation helps long-short factors more than long-only ones: keeping the sector component gave a better long-short factor in only 20% of trials. Read via a search summary. | [PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P165_Is_sector_neutrality.pdf) |
| S5 | Garleanu and Pedersen (2013), "Dynamic Trading with Predictable Returns and Transaction Costs", JF 68(6) | Academic | With costs the optimal policy trades only partway toward the target and aims ahead of it; costs slow trading. Motivates a turnover cap rather than trading to the target every month. | [EconPapers](https://econpapers.repec.org/RePEc:bla:jfinan:v:68:y:2013:i:6:p:2309-2340) |
| S6 | D'Avolio (2002), "The Market for Borrowing Stock", JFE 66 | Academic | About 91% of lent stocks cost under 1%/yr (general collateral, value-weighted mean 17 bp); about 9% are specials with mean 4.3%/yr; S&P 500 names are almost always general collateral. Our 25 bp flat fee is a general-collateral number. Figures from search excerpts. | [PDF](https://www.johnhcochrane.com/s/davolio_borrowing_stock_JF.pdf) |
| S7 | r/quant thread (March 2026, via a third-party Reddit mirror; mirror page NOT opened, content is a search snippet) | Forum | "Barra-neutralised" in practice means neutral to the shop's risk-model exposures: industry plus the main style factors, not only sector buckets; no industry standard. Weak evidence, used only to choose the constraint set. | [mirror](https://reddit.sentinel-team.org/posts/1rlotg7/snapshots/2026-03-05T23%3A48%3A32.033437Z) |
| S8 | skfolio documentation (factor models, MeanRisk) | Open-source docs | MeanRisk supports transaction costs, previous weights and constraints, so it is a reference implementation for a cost-aware mean-risk step. | [docs](https://skfolio.org/user_guide/factor_models.html.md) |
| S9 | Quantt, market-neutral strategies guide | Practitioner blog | A factor-neutral book removes value, momentum, size, quality, volatility and industry exposure and keeps stock-specific risk. | [guide](https://www.quantt.co.uk/resources/market-neutral-strategies-guide) |

**Gaps (stated).** No Reddit or StackExchange thread was opened and verified, so S7 is the only forum item and carries little weight. No free stock-loan fee history exists (borrow tiers are assumptions, swept). No head-to-head of a fundamental-factor vs PCA risk model on a free-data large-cap book was found, so v2 H2 is an original test. Free TNIC files key on Compustat gvkey and cannot be linked to SEC CIKs without paid data (v1 limitation), and building text peers from 10-K Item 1 for 1000 firms x 15 years is out of scope here.

## What industry does that v1 does not

1. Neutralises to a risk model's industry plus style exposures, not to industry dummies only (S2, S7, S9). v1 CN books were industry-neutral only and the composite loads on value, momentum and quality by construction.
2. Measures a book's risk against a fundamental factor model and reports the share of variance that is industry, style and specific (S2).
3. Caps turnover or trades partway to the target (S5), and checks that a risk-model constraint set does not inflate costs (S3).
4. Charges borrow by availability tier, not one flat fee (S6).
5. Reports participation in ADV and a capacity curve, not only a one-point $100M cost.
6. Audits the book family it searched (17 books plus robustness runs) for overfitting.

## v2 decisions

| # | Decision | Tag | Feeds |
|---|---|---|---|
| D1 | Build a small Barra-like model (FF49 industries + 8 styles) from panel characteristics; WLS daily cross-sections with lagged month-end exposures; Ledoit-Wolf factor covariance | **copy** idea, **fix** (free data) | Task 4 |
| D2 | Add industry + style neutral books (SN, SIN) and test net alpha with Romano-Wolf; do not assume neutrality helps (S4 says it should help long-short) | **fix** | H1 |
| D3 | Test the style model against v1's PCA-10 model on non-optimised decile-spread portfolios (QLIKE and bias), not on the books the optimiser tuned | **fix** | H2 |
| D4 | Add a hard monthly one-way turnover cap (10% of NAV) as a pre-set value, soft fallback flagged | **copy** (S5) | H3 |
| D5 | Tiered borrow (mcap rank: 25/50/150 bp), swept flat 25-400 bp, plus breakeven fee; label all as assumptions | **fix** (S6) | D1 table |
| D6 | ADV participation and NAV sweep with fixed weights (upper bound, stated) | **copy** | D2 table |
| D7 | PBO (CSCV) and deflated Sharpe over the 17 v1 books, and over 17 + new books; extend Romano-Wolf to new books | **copy** | H4 |
| D8 | skfolio MeanRisk as a cross-check of the cvxpy optimiser on sampled months, not the production solver | **copy** (S8) | Task 6 |
| D9 | SHAP on a gradient-boosted model of the 15 characteristics: exploratory, never headline | **copy** | E1 |
| D10 | Label every post-2019 figure `seen period (v1 reported it)`; state signal bar (month-end t, trade t+1 close) | **copy** (project rule) | README |

## Rejected ideas

| Idea | Why rejected |
|---|---|
| Use TNIC files directly | Keyed by gvkey; no free link to CIK (v1 limitation). Not rebuilt from 10-K text here. |
| Treat the r/quant snippet as evidence of an industry standard | The thread itself says there is none. |
| Replace the cvxpy optimiser by skfolio MeanRisk | Cannot express the per-name |dw|^1.5 impact term or the 1000-name factor-model covariance cheaply; kept as cross-check. |
| Tune the turnover cap or borrow tiers on 2012-2019 results | Values fixed before any v2 test (preregistration_v2.md). |
