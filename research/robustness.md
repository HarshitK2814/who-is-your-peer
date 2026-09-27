# Robustness (pre-registered variants; reported regardless of outcome)

Each variant is a full continuous backtest 2012-01 → 2026-07 with one pre-registered change. Tables:
`results/tables/robustness_test.csv`, `robustness_full.csv` (`scripts/robustness.py`). Sharpe ratios are net and annualised.
Romano–Wolf uses 2,000 bootstrap draws here (5,000 in the primary analysis; main-run p = 0.081 vs 0.080).

## Test period 2020–2023 (48 months)

| | main | costs × 2 | top-500 universe | no price momentum |
|---|---|---|---|---|
| C_ALL | 0.39 | 0.29 | 0.06 | 0.11 |
| C_FF49 | 0.15 | 0.01 | −0.26 | −0.27 |
| CN_FF49 | 0.15 | 0.01 | −0.01 | −0.12 |
| W_FF49 (within) | −0.02 | −0.13 | −0.31 | −0.33 |
| **B_FF49 (between)** | **0.68** | **0.63** | **0.70** | **0.66** |
| H1 min Romano–Wolf p | 0.081 | 0.120 | **0.004** | 0.090 |
| H2 SIC3 − FF49 | −0.23 | −0.23 | −0.13 | −0.23 |
| H2 RCLUST − FF49 | +0.10 | +0.04 | +0.03 | +0.06 |
| H3 CN − C (p) | +0.01 (0.96) | +0.01 (0.97) | +0.26 (**0.04**) | +0.15 (0.21) |
| C_FF49 modelled cost / yr | 0.8% | 1.7% | 0.5% | 0.8% |

## Full sample 2012–2026 (175 months; partly in-sample)

| | main | costs × 2 | top-500 universe | no price momentum |
|---|---|---|---|---|
| C_FF49 | −0.04 | −0.19 | −0.17 | −0.23 |
| B_FF49 | 0.17 | 0.12 | 0.41 | 0.14 |
| H1 min Romano–Wolf p | 0.29 | 0.35 | **0.048** | 0.34 |

## Reading
1. **The industry-bet (between) component is the most stable result in the study:** a test-period Sharpe of 0.63–0.70
   in every variant. The within-industry and composite books are fragile: they flip sign with the universe or with
   momentum removed.
2. **Among the 500 largest stocks, the industry-bet premium is statistically significant** in the test period
   (p = 0.004) and marginally over the full sample (p = 0.048). There, industry neutrality also *helped* the composite
   (H3 p = 0.04). This is one of three robustness variants and was not the primary test, so it should be read as
   *suggestive evidence against the filings' claim in large caps*, pending a survivorship-free (CRSP) replication.
   The large-cap universe is also the one least affected by our survivorship bias.
3. **Price momentum matters to the composite:** without it, the test-period composite Sharpe falls from 0.15 to −0.27.
   Vanguard QEG states its approach is "not technical analysis of stock price movements", so a closer reconstruction of
   its process (without momentum) would have done worse here.
4. **Doubling costs** removes most of the composite's small test-period edge (0.15 → 0.01) but barely affects the
   between-industry book (0.68 → 0.63), which trades less (15% vs 20% monthly turnover).
