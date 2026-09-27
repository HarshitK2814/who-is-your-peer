"""Render video/composition.html to an MP4, frame by frame (deterministic, no screen capture).

    python scripts/render_video.py                      # full video, 30 fps, 1080x1350
    python scripts/render_video.py --stills 3 27 37 52  # only a few preview frames

The composition exposes window.render(t) which sets every element for time t, so each frame is exact.
Data comes from docs/showcase_data.json and docs/showcase_3d.json (the same numbers as the showcase page).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "video"
NAME = "Harshit Kumar"
HANDLE = "github.com/HarshitK2814 · interactive version in the repo"


def build_html() -> Path:
    page = (VIDEO / "composition.html").read_text(encoding="utf-8")
    data = (ROOT / "docs" / "showcase_data.json").read_text(encoding="utf-8").replace("</", "<\\/")
    data3d = (ROOT / "docs" / "showcase_3d.json").read_text(encoding="utf-8").replace("</", "<\\/")
    page = page.replace("/*DATA3D*/", data3d).replace("/*DATA*/", data).replace("/*NAME*/", NAME.upper()).replace("/*HANDLE*/", HANDLE)
    out = VIDEO / "build" / "composition_built.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--stills", nargs="*", type=float)
    a = ap.parse_args()
    html = build_html()
    frames = VIDEO / "build" / "frames"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True,
                                    args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--force-device-scale-factor=1"])
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        logs = []
        page.on("console", lambda m: logs.append(m.text))
        page.on("pageerror", lambda e: logs.append("PAGE ERROR: " + str(e)))
        page.goto(html.as_uri())
        page.wait_for_function("window.ready !== undefined")
        page.evaluate("window.ready")
        duration = page.evaluate("window.DURATION")
        print("\n".join(l for l in logs if "check" in l or "ERROR" in l))
        stage = page.locator("#stage")
        if a.stills:
            for t in a.stills:
                page.evaluate(f"window.render({t})")
                stage.screenshot(path=str(VIDEO / f"still_{t:05.1f}s.png"))
            print("stills written to", VIDEO)
            browser.close()
            return
        if frames.exists():
            shutil.rmtree(frames)
        frames.mkdir(parents=True)
        n = int(round(duration * a.fps))
        t0 = time.time()
        for i in range(n):
            page.evaluate(f"window.render({i / a.fps})")
            stage.screenshot(path=str(frames / f"f{i:05d}.jpg"), type="jpeg", quality=93)
            if i % 150 == 0:
                print(f"frame {i}/{n}  {time.time() - t0:.0f}s", flush=True)
        # poster for the LinkedIn cover
        page.evaluate("window.render(29.0)")
        stage.screenshot(path=str(VIDEO / "poster.png"))
        browser.close()
    out = VIDEO / "who_is_your_peer_linkedin.mp4"
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", str(frames / "f%05d.jpg"),
                    "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-color_range", "tv", "-colorspace", "bt709",
                    "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-movflags", "+faststart",
                    str(out)], check=True)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {n} frames, {duration:.0f}s)")


if __name__ == "__main__":
    main()
