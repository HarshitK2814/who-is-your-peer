# Literature Review

## 1. Industry-relative characteristics and the value of industry bets
* **Asness, Porter & Stevens (2000)**, "Predicting Stock Returns Using Industry-Relative Firm Characteristics"
  (AQR working paper). Within-industry versions of value and other characteristics predict returns better than
  raw versions, and industry-level components behave differently (e.g. industry value is weak). This is the closest
  precedent for our within/between decomposition. We extend it to a *multi-theme institutional composite* traded
  in a *cost-aware beta-neutral book*, and add more peer definitions.
* **Moskowitz & Grinblatt (1999, JF)**, "Do Industries Explain Momentum?" A large share of momentum profits
  is an industry effect. This is a counterpoint to the filings' claim for the *sentiment* theme specifically.
* **Hou (2007, RFS)**, "Industry Information Diffusion and the Lead-Lag Effect in Stock Returns": industry-wide
  news diffuses slowly across firms in an industry. This is the most plausible channel for our post-hoc finding that the
  industry-level *sentiment* component (earnings surprises) drives the industry-bet premium.
* **Novy-Marx (2013, JFE)**, gross profitability. Profitability is strongest when measured relative to industry.

## 2. Peer definitions
* **Hoberg & Phillips (2016, JPE)**, "Text-Based Network Industries and Endogenous Product Differentiation"
  (TNIC): 10-K product-description peers outperform SIC in explaining firm characteristics.
* **Hoberg & Phillips (2018, JFQA)**, "Text-Based Industry Momentum": shocks to less-visible text-based peers
  drive momentum. *Not used here*: the free TNIC files are keyed by Compustat gvkey (see EXP-000).
* **Lee, Ma & Wang (2015, JFE)**, "Search-Based Peer Firms": EDGAR co-search peers beat GICS.
* **Avramov, Ge, Li & Linton (2026, JFE)**, "Dual Peer Effects and Cross-Stock Predictability": both peer-group
  strength and a firm's position within its group predict returns (a between- and within-effect together).

## 3. The characteristics behind the five themes
| Theme | Characteristic | Source |
|---|---|---|
| Quality | Gross profitability | Novy-Marx (2013) |
| Quality | Accruals | Sloan (1996); Hribar & Collins (2002) cash-flow accruals |
| Management decisions | Net external financing | Bradshaw, Richardson & Sloan (2006) |
| Management decisions | Net share issuance | Pontiff & Woodgate (2008) |
| Management decisions | Asset growth | Cooper, Gulen & Schill (2008) |
| Growth | Earnings persistence / sales growth | Lakonishok, Shleifer & Vishny (1994) (growth vs value) |
| Sentiment | 12-1 momentum | Jegadeesh & Titman (1993) |
| Sentiment | SUE / post-earnings drift | Bernard & Thomas (1989) |
| Valuation | E/P, B/M, CF/P, S/P | Fama & French (1992); Lakonishok, Shleifer & Vishny (1994) |

Replicability of such signals: **Chen & Zimmermann (2022, Critical Finance Review)** ("Open Source Cross-Sectional
Asset Pricing"); post-publication decay: **McLean & Pontiff (2016, JF)**.

## 4. Portfolio construction and evaluation
* **Grinold & Kahn**, *Active Portfolio Management*: alpha = IC × volatility × score; transfer coefficient.
* **Frazzini, Israel & Moskowitz (2018)**, "Trading Costs": realised institutional costs are far below naive estimates.
  That is a reason our modelled costs could be conservative.
* **Abdi & Ranaldo (2017, RFS)**: spread estimator from close/high/low prices (used here).
* **Ledoit & Wolf (2008, JEF)**: robust Sharpe-ratio difference tests. **Romano & Wolf (2005, Econometrica)**:
  stepwise multiple testing. **Politis & Romano (1994)**: stationary bootstrap. **Bailey & López de Prado (2014)**:
  deflated Sharpe ratio. **Harvey, Liu & Zhu (2016, RFS)**: higher t-hurdles for factor claims.

## 5. Gap addressed
The existing literature shows industry-relative signals are often better *individually*. We found limited evidence of
a test that (i) takes a *disclosed institutional* five-theme composite, (ii) splits it into within- and between-industry
components under several peer definitions, and (iii) evaluates both as beta-neutral books with costs, borrow and a
frozen pre-registration. The novelty claim is limited to that new empirical comparison. The finding itself would be
an extension of Asness, Porter & Stevens (2000), not a new phenomenon.
