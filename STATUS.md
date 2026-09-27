# P1 status: Who Is Your Peer? (COMPLETE, paused 2026-09-27)

## Where it stands
- Research complete: pre-registered H1–H3 tested on the locked 2020–23 test period, robustness done, two post-hoc studies done.
- Git: 3 commits (scaffold → dev/val → `b071a78 prereg: freeze`). **About 50 files since then are uncommitted** (test results,
  post-hoc work, showcase, video, notebook). The user said not to commit yet. **Nothing has been pushed.**

## Headline results (test 2020–23, 48 months, net of costs, $100M NAV, beta-neutral)
| Item | Result |
|---|---|
| H1 industry bets (B_FF49) | Sharpe 0.68 [−0.31, 1.67], Romano–Wolf p 0.085 → the filing's claim survives at 5% |
| H2 peer definition matters | Fails (SIC3−FF49 −0.23, Holm p 0.14) |
| H3 industry neutrality matters | Fails (+0.01, p 0.96) |
| Composite, full sample 2012–26 | Sharpe ≈ 0.01, no reliable net alpha |
| Post-hoc: beta leak | realised β 0.15; hedged Sharpe 0.68 → 0.46; no leak in the top-500 universe (hedged 0.68) |
| Post-hoc: driver | not industry momentum; industry sentiment + management themes carry it |
| Survivorship | universe covers ~55% (2011) → 82% (2020) → 93% (2023) of large firms |

## Deliverables
- `research/`: paper, pre-registration, results, robustness, limitations, experiment log (EXP-000…010), post-hoc notes.
- `docs/index.html`: interactive 3D explorer (data: `docs/showcase_data.json`, `docs/showcase_3d.json`).
- `video/v2/who_is_your_peer_launch.mp4`: 81 s LinkedIn launch video with no company or personal names. v1 names the asset manager: do not post it.
- `notebooks/01_results_overview.ipynb`; the programme website lives in `../website/`.

## Open items (optional)
- Commit the post-freeze work when the user asks, in a few logical commits, and push only when asked.
- Research docs and the explorer still name the asset manager (source citation); the paper byline has the user's name.
- Future work (paper §11): CRSP replication via WRDS (the user is checking university access), text-based peers from 10-K Item 1.
