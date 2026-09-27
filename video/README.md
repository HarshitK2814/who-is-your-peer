# Launch video

**Use `v2/who_is_your_peer_launch.mp4`**: 1080×1350 (4:5), ~81 s, 30 fps, H.264 + AAC, voiceover and music,
captions burned in, loudness −14 LUFS. No company or personal names. Cover image: `v2/poster.png`.
(`who_is_your_peer_linkedin.mp4` is the earlier silent v1 and names the asset manager; don't post it.)

## How v2 is made (all free tools, fully reproducible)
| Step | Script | What it does |
|---|---|---|
| 1 | `scripts/make_voiceover.py` | Neural voiceover (edge-tts, "Andrew") per segment from `v2/script.json`, with word timings for captions |
| 2 | `scripts/record_site.py` | Frame-by-frame screen recording of `docs/index.html` with a scripted cursor: clicks, tooltip sweeps, 3D playback and rotation |
| 3 | `scripts/make_music.py` | Timeline from the voice timings + original 100 BPM music whose arrangement follows the story (no samples, no licensing) |
| 4 | `scripts/render_video_v2.py` | Renders `v2/composition.html` frame by frame (cursor-following zoom on the recordings), mixes voice + ducked music, encodes MP4 |

Story arc (the standard startup launch structure): problem → gap → what we built → live demo → result → twist →
3D demo → call to action. Every number shown is computed from the backtest data at render time.

## Suggested post text

> Almost every quant fund forces its portfolio to be industry-neutral. One of the world's largest asset managers
> told regulators why: "sector bets don't add value."
>
> I wanted to know if that's true, using only free public data.
>
> I rebuilt a five-theme stock model from 2.7M point-in-time filing facts, split it into "picking stocks within
> industries" and "betting on industries", and ran both as market-neutral portfolios with trading costs. I locked the
> 2020–23 test period in code until my hypotheses were committed.
>
> • Industry bets earned a Sharpe of 0.68 in the locked test (p = 0.085). The claim survives, narrowly.
> • The "market-neutral" portfolio wasn't: its real market beta was 0.15. Hedged, the Sharpe falls to 0.46.
> • What's left comes from industry-wide earnings news, not industry momentum.
>
> The lesson: a constraint that holds on paper can fail in reality, and you only find out if you check.
>
> Code, pre-registration, experiment log (bugs included) and the interactive 3D version: [link]
>
> #QuantitativeFinance #QuantResearch #Python #SystematicTrading
