"""Render the v2 launch video: frames (headless Edge) + voiceover + ducked music -> MP4.

Pipeline:  make_voiceover.py -> record_site.py -> make_music.py -> render_video_v2.py
    python scripts/render_video_v2.py --stills 5 16 26 36 45 53 58 66 76   # preview frames
    python scripts/render_video_v2.py                                     # full render
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "video" / "v2"
BUILD = V2 / "build"
FPS = 30


def build_html() -> Path:
    tl = (V2 / "timeline.json").read_text(encoding="utf-8")
    meta = {s: json.loads((V2 / "rec" / s / "meta.json").read_text()) for s in ("demo", "twist", "threed")}
    meta = {s: {"frames": m["frames"], "log": m["log"]} for s, m in meta.items()}
    data = (ROOT / "docs" / "showcase_data.json").read_text(encoding="utf-8")
    page = (V2 / "composition.html").read_text(encoding="utf-8")
    page = page.replace("/*TIMELINE*/", tl).replace("/*RECMETA*/", json.dumps(meta)).replace("/*DATA*/", data.replace("</", "<\\/"))
    BUILD.mkdir(parents=True, exist_ok=True)
    out = BUILD / "composition_built.html"
    out.write_text(page, encoding="utf-8")
    return out


def mix_audio(total: float) -> Path:
    tl = json.loads((V2 / "timeline.json").read_text(encoding="utf-8"))
    inputs, parts = [], []
    for k, s in enumerate(tl["segments"]):
        inputs += ["-i", str(V2 / "audio" / f"{s['id']}.mp3")]
        ms = int(s["start"] * 1000)
        parts.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
    n = len(tl["segments"])
    inputs += ["-i", str(V2 / "audio" / "music.wav")]
    vo = "".join(f"[v{k}]" for k in range(n))
    filt = ";".join(parts) + (
        f";{vo}amix=inputs={n}:normalize=0,apad=whole_dur={total}[vo]"
        f";[vo]asplit=2[vo1][vosc]"
        f";[{n}:a]volume=0.55[mus]"
        f";[mus][vosc]sidechaincompress=threshold=0.02:ratio=8:attack=25:release=450:makeup=1[duck]"
        f";[vo1][duck]amix=inputs=2:normalize=0,atrim=0:{total},loudnorm=I=-14:TP=-1.0:LRA=9[out]")
    out = BUILD / "mix.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", filt, "-map", "[out]",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)], check=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", nargs="*", type=float)
    a = ap.parse_args()
    html = build_html()
    total = json.loads((V2 / "timeline.json").read_text())["total"]
    frames = BUILD / "frames"
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True, args=["--allow-file-access-from-files"])
        page = b.new_page(viewport={"width": 1080, "height": 1350})
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(html.as_uri())
        page.wait_for_function("window.ready !== undefined")
        page.evaluate("window.ready")
        stage = page.locator("#stage")
        if a.stills:
            for t in a.stills:
                # warm the camera follow for ~1s before the still so zooms look as they will in motion
                for k in range(30, 0, -1):
                    page.evaluate(f"window.render({max(0, t - k / FPS)}, {int((t - k / FPS) * FPS)})")
                page.evaluate(f"window.render({t}, {int(t * FPS)})")
                stage.screenshot(path=str(BUILD / f"still_{t:05.1f}.png"))
            print("stills ->", BUILD, errs[:3])
            b.close()
            return
        if frames.exists():
            shutil.rmtree(frames)
        frames.mkdir(parents=True)
        n = int(round(total * FPS))
        t0 = time.time()
        for i in range(n):
            page.evaluate(f"window.render({i / FPS}, {i})")
            stage.screenshot(path=str(frames / f"f{i:05d}.jpg"), type="jpeg", quality=93)
            if i % 300 == 0:
                print(f"frame {i}/{n} {time.time() - t0:.0f}s", flush=True)
        page.evaluate(f"window.render({json.loads((V2 / 'timeline.json').read_text())['segments'][4]['start'] + 5.0}, 0)")
        stage.screenshot(path=str(V2 / "poster.png"))
        print("page errors:", errs[:3])
        b.close()
    audio = mix_audio(total)
    out = V2 / "who_is_your_peer_launch.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(frames / "f%05d.jpg"), "-i", str(audio),
                    "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-color_range", "tv", "-colorspace", "bt709",
                    "-color_primaries", "bt709", "-color_trc", "bt709", "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-maxrate", "6M", "-bufsize", "12M",
                    "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
