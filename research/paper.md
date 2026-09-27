# Do Sector Bets Add Value? Testing an SEC-Disclosed Claim with Industry-Relative Multi-Theme Signals

*Harshit Kumar — research write-up, September 2026. Code and data pipeline: this repository.*

## Abstract
Vanguard's Quantitative Equity Group states in SEC filings that its five-theme equity model ranks stocks against
industry peers and that "sector bets do not add value over the long term". We reconstruct a five-theme composite
(growth, quality, management decisions, sentiment, valuation) from as-first-reported SEC XBRL data, split it into
within-industry and between-industry components under four peer definitions, and trade each as a beta-neutral
long/short book with a factor risk model, spread and impact costs, and borrow fees. With hypotheses frozen in git
before the 2020–2023 test period, the industry-bet component earned a net Sharpe ratio of 0.68 (95% CI −0.31 to
1.67; Romano–Wolf p = 0.085), so the filing's claim is not rejected at the 5% level. The component then reversed in
2024–2026 (−0.35). Peer definition (FF49 vs SIC-3 vs return clusters) and explicit industry neutrality make no
detectable difference. The reconstructed composite has no reliable net alpha over 2012–2026. All results use free
data and carry a measured survivorship bias.

## 1. Introduction
Industry neutrality is one of the most common constraints in institutional quantitative equity. It is usually
justified empirically: industry exposures add risk but not return. That justification is rarely tested openly,
and never against the specific claim a manager makes. A disclosed statement in a regulatory filing gives a concrete,
falsifiable target.

## 2. Institutional motivation
See `institutional_methodology.md` for verbatim quotes. Three filings are used: the 2020 N-CSR (five themes, peer-relative
ranking, sector neutrality "because our research has shown that sector bets do not add value over the long term"),
the 2019 N-CSR (minimising "risks that our research indicates don't improve returns (such as industry selection…)"),
and the 2026 497K (beta neutrality only; the advisor "may emphasize specific industries"). We separate what is disclosed
(Layer A) from our reconstruction (Layer B) and our extension (Layer C).

## 3. Literature
Industry-relative characteristics (Asness, Porter & Stevens 2000), industry momentum (Moskowitz & Grinblatt 1999),
text-based peers (Hoberg & Phillips 2016, 2018), search-based peers (Lee, Ma & Wang 2015), and dual peer effects
(Avramov, Ge, Li & Linton 2026). See `literature_review.md`.

## 4. Data and methodology
* **Fundamentals:** SEC `companyfacts.zip`; every value is as first reported, and usable only from the day after its filing.
  Discrete quarters come from YTD differencing, and TTM from four quarters. Cover-page share counts are corrected for
  ×1000 tagging errors.
* **Prices:** Yahoo Finance (split/dividend-adjusted), CIK-linked via the SEC ticker file.
* **Characteristics (15) → themes (5):** see `src/peerrel/signals/scores.py`. Each is rank-Gaussian within peer
  group, averaged within theme, then equal-weighted.
* **Decomposition:** raw composite S = W + B with B the peer-group mean.
* **Portfolio:** α = 0.03·σ_idio·score; max α'w − λw'Σw − costs subject to β'w = 0, ‖w‖₁ ≤ 2, |w_i| ≤ 1%, ADV cap;
  Σ = 10-factor PCA + idiosyncratic; λ calibrated on development months only.
* **Timing:** signal at the month-end close; trade at the next close; hold one month.

## 5. Experimental design
Universe: top 1000 non-financial NYSE/Nasdaq stocks, price ≥ $5. Development 2012–16, validation 2017–19,
test 2020–23 (locked in code until the pre-registration commit), recent 2024–26. Seventeen pre-specified books.
Primary test: Romano–Wolf stepdown over the four between-peer books; secondary: HAC Sharpe-difference tests.

## 6. Results
See `results.md` for full tables. Test period, net Sharpe: C_ALL 0.39, C_FF49 0.15, CN_FF49 0.15, W_FF49 −0.02,
B_FF49 0.68. Full 2012–26: composites ≈ 0 (C_FF49 −0.04 [−0.56, 0.47]); B_FF49 0.17. Validation 2017–19: composites
−1.4 to −1.7 (value drawdown).

## 7. Statistical analysis
H1 Romano–Wolf p 0.080–0.109 (not significant); deflated Sharpe of the best industry-bet book 0.32. H2 Holm p 0.14 / 0.60.
H3 p 0.96. A 48-month test has little power: Sharpe differences below about 0.8 are not reliably detectable.

## 8. Robustness
See `robustness.md`. The industry-bet book's test Sharpe is 0.63–0.70 under 2× costs, a 500-stock universe and a
composite without momentum. In the 500-stock universe it is significant (Romano–Wolf p = 0.004), which is suggestive
evidence against the claim among large caps. The composite is fragile (−0.27 to 0.15).

## 8b. Post-hoc analysis (exploratory)
The industry-bet premium is not industry momentum (Moskowitz–Grinblatt factor loading −0.07, t −0.56). However, the
industry-bet book, constrained to zero ex-ante beta each month, had a realised market beta of 0.19 (t 3.9): daily-return
betas understate true betas, and industry-level bets concentrate that error. Hedging with a trailing 36-month beta (no
look-ahead) lowers its test Sharpe from 0.68 to 0.46. In the 500-largest-stock universe there is no leak and the premium
survives (0.68 test, 0.39 full), partly explained by CMA. Ex-ante neutrality constraints need ex-post verification.

Decomposing the industry-bet book by theme (also post hoc) shows the premium is concentrated, not diffuse: the
industry-level sentiment component (earnings surprises and momentum) is the most persistent contributor and is nearly
uncorrelated with the industry-momentum factor. That points toward slow diffusion of industry-wide earnings news rather
than price momentum. Industry-level management decisions contributed in 2020–23, the quality component was a consistent
drag, and the leaked market beta sits mainly in the valuation component.

## 9. Limitations
Survivorship bias (universe coverage 54% in 2012 → 93% in 2023 of then-listed large firms), current SIC codes, modelled
costs and borrow, reconstructed (not actual) theme variables, and a short sample. See `limitations.md`.

## 10. Conclusion
The claim that sector bets do not add value is not contradicted, but neither is it supported in the strong sense
"industry exposure earns zero". The industry-bet component was highly profitable in 2020–23 and unprofitable in
2024–26, with low correlation to within-industry selection. In a sample this short, the neutralise-or-not choice is
statistically undecidable in the primary universe. Among the 500 largest stocks (a pre-registered robustness arm, and
the part of the universe least affected by survivorship), the industry-bet premium is significant. That is the most
promising lead for a survivorship-free replication. How a composite is split matters more for *when* it makes money
than for *whether* it does.

## 11. Future work
(1) CRSP/Compustat replication back to 1990 (survivorship-free, long sample). (2) Text-based peers built directly from
10-K Item 1 text on EDGAR (free, but heavy to process). (3) Theme-level decomposition: which themes' industry components
carry the premium (e.g. momentum vs value)? (4) Conditioning the industry component on dispersion regimes, pre-registered.
