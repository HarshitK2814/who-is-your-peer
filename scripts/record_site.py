"""Frame-by-frame 'screen recording' of the showcase site (docs/index.html) with a scripted cursor.

Each scene is a list of timed actions; at every frame the director moves the cursor (eased), fires clicks
exactly on schedule, sweeps chart hovers and turns 3D cameras, then takes a screenshot. Deterministic and
crisp (device scale 2), unlike a real-time screen capture.

    python scripts/record_site.py              # all scenes -> video/v2/rec/<scene>/f00000.jpg ...
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "video" / "v2" / "rec"
FPS = 30
VIEW = {"width": 1100, "height": 720}

CURSOR_JS = """
(() => {
  // company names are not shown in the video
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const rep = [[/Vanguard's quantitative equity team/g, "A major asset manager's quant team"], [/Vanguard Market Neutral Fund[^·]*·/g, ""],
               [/Vanguard Montgomery Funds \\(CIK 1409957\\) ·/g, ""], [/Vanguard/g, "A major asset manager"]];
  let n; while ((n = walker.nextNode())) { let s = n.nodeValue; for (const [a, b] of rep) s = s.replace(a, b); n.nodeValue = s; }
  const c = document.createElement("div");
  c.id = "fakecursor";
  c.innerHTML = '<svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8.5 16 L12 24 L15.5 22.5 L12 14.8 L19.5 14.8 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, { position: "fixed", left: "0px", top: "0px", zIndex: 99999, pointerEvents: "none", filter: "drop-shadow(0 2px 4px rgba(0,0,0,.35))" });
  const r = document.createElement("div");
  r.id = "fakeripple";
  Object.assign(r.style, { position: "fixed", width: "44px", height: "44px", marginLeft: "-22px", marginTop: "-22px", borderRadius: "50%",
    border: "2.5px solid #2a78d6", background: "rgba(42,120,214,0.12)", zIndex: 99998, pointerEvents: "none", opacity: 0 });
  document.body.append(r, c);
  window.__cursor = (x, y) => { c.style.left = x + "px"; c.style.top = y + "px"; };
  window.__ripple = (x, y, p) => { r.style.left = x + "px"; r.style.top = y + "px"; r.style.opacity = p > 0 && p < 1 ? (1 - p) : 0;
                                   r.style.transform = `scale(${0.4 + 1.1 * p})`; };
  window.__center = (sel, text) => {
    let el = null;
    if (text) el = [...document.querySelectorAll(sel)].find((b) => b.textContent.trim() === text);
    else el = document.querySelector(sel);
    if (!el) return null;
    const b = el.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2, b.left, b.width, b.top, b.height];
  };
  window.__click = (sel, text) => { const el = [...document.querySelectorAll(sel)].find((b) => !text || b.textContent.trim() === text); if (el) el.click(); };
  window.__hover = (sel, fx, fy) => {
    const el = document.querySelector(sel); if (!el) return;
    const hit = [...el.querySelectorAll("rect")].pop(); const b = hit.getBoundingClientRect();
    const x = b.left + fx * b.width, y = b.top + fy * b.height;
    hit.dispatchEvent(new PointerEvent("pointermove", { clientX: x, clientY: y, bubbles: true }));
    return [x, y];
  };
})();
"""


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


class Director:
    def __init__(self, page, scene: str):
        self.page, self.scene = page, scene
        self.out = REC / scene
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        self.cur = [VIEW["width"] + 40, VIEW["height"] * 0.7]
        self.frame = 0
        self.click_at = None
        self.log = []

    def center(self, sel, text=None):
        c = self.page.evaluate("([s, t]) => window.__center(s, t)", [sel, text])
        if c is None:
            raise RuntimeError(f"{self.scene}: element not found {sel} {text}")
        return c[:2]

    def snap(self, extra=None):
        t = self.frame / FPS
        if extra:
            extra(t)
        self.page.evaluate("([x, y]) => window.__cursor(x, y)", self.cur)
        p = (t - self.click_at[2]) / 0.45 if self.click_at else -1
        if self.click_at:
            self.page.evaluate("([x, y, p]) => window.__ripple(x, y, p)", [self.click_at[0], self.click_at[1], p])
        self.page.screenshot(path=str(self.out / f"f{self.frame:05d}.jpg"), type="jpeg", quality=92)
        self.log.append({"f": self.frame, "cursor": [round(v, 1) for v in self.cur]})
        self.frame += 1

    def hold(self, secs, extra=None):
        for _ in range(int(round(secs * FPS))):
            self.snap(extra)

    def move(self, target, secs, extra=None):
        start, n = list(self.cur), max(1, int(round(secs * FPS)))
        for i in range(n):
            e = ease((i + 1) / n)
            arc = math.sin(e * math.pi) * 18          # slight human arc
            self.cur = [start[0] + (target[0] - start[0]) * e, start[1] + (target[1] - start[1]) * e - arc]
            self.snap(extra)

    def click(self, sel, text=None, extra=None):
        x, y = self.center(sel, text)
        self.click_at = (x, y, self.frame / FPS)
        self.page.evaluate("([s, t]) => window.__click(s, t)", [sel, text])
        self.page.wait_for_timeout(60)
        self.hold(0.35, extra)

    def sweep(self, chart_sel, secs, fy=0.55, f0=0.05, f1=0.95, extra=None):
        n = int(round(secs * FPS))
        for i in range(n):
            fx = f0 + (f1 - f0) * ease((i + 1) / n)
            xy = self.page.evaluate("([s, fx, fy]) => window.__hover(s, fx, fy)", [chart_sel, fx, fy])
            self.cur = xy
            self.snap(extra)

    def done(self):
        (self.out / "meta.json").write_text(json.dumps({"frames": self.frame, "fps": FPS, "view": VIEW, "log": self.log}))
        print(f"{self.scene}: {self.frame} frames ({self.frame / FPS:.1f}s)")


def scroll_to(page, anchor: str, offset: int = 24):
    page.evaluate("([a, o]) => { const el = document.querySelector(a); window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - o); }",
                  [anchor, offset])
    page.wait_for_timeout(200)


def record_demo(page):
    """Explorer: period -> hedge -> universe, then sweep the chart tooltip."""
    scroll_to(page, "#explorer .panel", 20)
    d = Director(page, "demo")
    d.hold(0.3)
    d.move(d.center("#c-period button", "Test 20–23"), 1.0); d.click("#c-period button", "Test 20–23")
    d.hold(0.35)
    d.move(d.center("#c-hedge button", "Beta-hedged"), 0.8); d.click("#c-hedge button", "Beta-hedged")
    d.hold(0.35)
    d.move(d.center("#c-universe button", "Top 500"), 0.8); d.click("#c-universe button", "Top 500")
    d.hold(0.3)
    d.move(d.center("#ch-main svg"), 0.7)
    d.sweep("#ch-main", 3.0, fy=0.45)
    d.hold(0.6)
    d.done()


def record_twist(page):
    """Beta section: sweep the as-traded vs hedged lines, then switch universe to show the beta disappear."""
    page.evaluate("() => window.__click('#c-universe button', 'Top 1000')")
    scroll_to(page, "#beta .panel", 20)
    d = Director(page, "twist")
    d.hold(0.3)
    d.move(d.center("#ch-beta svg"), 0.9)
    d.sweep("#ch-beta", 4.2, fy=0.35, f0=0.05, f1=0.93)
    d.move(d.center("#c-beta-universe button", "Top 500"), 0.9); d.click("#c-beta-universe button", "Top 500")
    d.move(d.center("#tb-beta"), 0.8)
    d.hold(2.0)
    d.done()


def record_3d(page):
    """Industry landscape playing through the test period while rotating, then the peer map."""
    scroll_to(page, "#three-d .panel", 16)
    d = Director(page, "threed")
    start = page.evaluate("() => { const s = document.getElementById('ls-slider'); return +s.value; }")
    first = page.evaluate("() => [...Array(200).keys()].find(i => i >= 0)")  # noqa: F841  (keeps API symmetrical)

    def landscape(t):
        idx = int(min(start + 44, start + t * 8))           # ~8 months per second through the test period
        ang = -0.8 + 0.25 * t
        page.evaluate("""([i, a]) => { const s = document.getElementById('ls-slider'); s.value = i;
            s.dispatchEvent(new Event('input')); Plotly.relayout('p-landscape', {'scene.camera': {eye: {x: 1.55*Math.cos(a), y: 1.55*Math.sin(a), z: 0.7}}}); }""",
                      [idx, ang])
        page.wait_for_timeout(15)

    d.move(d.center("#ls-play"), 0.8, extra=landscape)
    d.click_at = (*d.center("#ls-play"), d.frame / FPS)
    d.hold(5.2, extra=landscape)
    d.move(d.center("#c-3d-tab button", "Peer map"), 0.7)
    d.click("#c-3d-tab button", "Peer map")
    page.wait_for_timeout(400)

    def peers(t):
        ang = 0.6 + 0.35 * (t - 6.9)
        page.evaluate("(a) => Plotly.relayout('p-peers', {'scene.camera': {eye: {x: 1.5*Math.cos(a), y: 1.5*Math.sin(a), z: 0.62}}})", ang)
        page.wait_for_timeout(15)

    d.hold(1.2, extra=peers)
    buttons = page.evaluate("() => [...document.querySelectorAll('#c-cluster button')].map(b => b.textContent.trim())")
    d.move(d.center("#c-cluster button", buttons[2]), 0.7, extra=peers)
    d.click("#c-cluster button", buttons[2], extra=peers)
    d.hold(2.2, extra=peers)
    d.done()


def main() -> None:
    url = (ROOT / "docs" / "index.html").resolve().as_uri()
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = b.new_context(viewport=VIEW, device_scale_factor=2, color_scheme="light")
        page = ctx.new_page()
        page.goto(url)
        page.wait_for_function("window.Plotly !== undefined")
        page.wait_for_timeout(1500)
        page.evaluate(CURSOR_JS)
        page.wait_for_timeout(300)
        record_demo(page)
        record_twist(page)
        record_3d(page)
        b.close()


if __name__ == "__main__":
    main()
