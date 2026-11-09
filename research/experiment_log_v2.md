# Experiment log v2 (P1). v1 log (EXP-000..010) is sealed.

| ID | Date | What | Outcome |
|---|---|---|---|
| V2-001 | 2026-11-09 | Evidence file, v2 pre-registration (hash `b83921d49b3c`), configs, qcore sync (validation, risk, forward split; diff vs root was additive only; qengine not vendored: P1 is a monthly stock book with its own optimiser) | Frozen in commit `prereg-v2: freeze` before any v2 test |
| V2-002 | 2026-11-09 | Style model built (FF49 + 8 styles, daily WLS, Ledoit-Wolf). Clarification made before any hypothesis statistic: the style universe for exposure standardisation is the top 1,500 names by market cap (eligible filter), not 1,000, so every backtest-universe name has an exposure; backtest universe unchanged | Infrastructure only |
| V2-003 | 2026-11-09 | Parity: v2 runner with options off vs sealed v1 C_FF49, first 3 months (pytest) and all 175 months (results_v2.md) | Max monthly difference about 1e-5 (solver tolerance) |
| V2-004 | 2026-11-09 | **Bug/robustness fix after freeze.** First full v2 run: Clarabel raised numerical SolverErrors in 9 V0, 8 SIN, 2 SN and 2 P_FF49 months and the book was traded flat (no ECOS fallback in this env; v1 ran where ECOS existed). Fix: retry ladder (rescaled objective, then looser tolerances) in `src/peerrel/v2/portfolio.py`. No hypothesis statistic had been computed (only per-book means were glanced at). Both runs kept; design-period Sharpes before/after are in results_v2.md | After the fix: 0 failed months in all books; P_FF49 reproduces v1 |
| V2-005 | 2026-11-09 | H1-H4, D1, D2, D4, E1 run once each on the frozen definitions | All four hypotheses NOT SUPPORTED (results_v2.md) |
| V2-006 | 2026-11-09 | Capacity rule "Sharpe within 0.10 of the $100M value" is ill-defined when the design-period Sharpe is negative; reported with that caveat rather than changed | Stated in results_v2.md |
| V2-007 | 2026-11-09 | skfolio MeanRisk vs cvxpy on 3 sampled months (150 names, linear costs): weight correlation above 0.99999 | Formulation and solver cross-checked |
| V2-008 | 2026-11-09 | Forward tracker written and tested on synthetic data. Panel ends 2026-08, so no forward month exists yet | Waiting for 2026-11 signal |

## Decisions made autonomously (no user available)
- Branch is `master` (the only branch on the remote); pushes go there.
- Text-based (Hoberg-Phillips) peers not rebuilt: needs 10-K Item 1 text for about 1,000 firms x 15 years; recorded as future work.
- Borrow tiers (25/50/150 bp) are assumptions; D'Avolio (2002) puts general collateral near 17 bp and specials near 4.3%.
