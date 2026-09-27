"""Timeline + original background music for the v2 video (no samples, no licensing issues).

1. Builds video/v2/timeline.json from the voiceover timings: each segment starts after the previous one
   plus a short breath, with a lead-in and a tail.
2. Synthesises a 100 BPM track in A minor (Am-F-C-G) whose arrangement follows the story:
   pads under the hook -> plucked arpeggio from the 'gap' -> soft beat from 'solution' ->
   breakdown on the 'twist' -> full again for 3D -> resolve and fade on the call to action.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "video" / "v2"
SR = 44100
BPM = 100
BEAT = 60 / BPM
LEAD, GAP, TAIL = 0.8, 0.5, 2.4


def build_timeline() -> dict:
    timing = json.loads((V2 / "timing.json").read_text(encoding="utf-8"))["segments"]
    t, segs = LEAD, []
    for s in timing:
        segs.append({"id": s["id"], "start": round(t, 3), "end": round(t + s["duration"], 3), "duration": s["duration"],
                     "captions": [{"text": c["text"], "start": round(t + c["start"], 3), "end": round(t + c["end"], 3)} for c in s["captions"]]})
        t += s["duration"] + GAP
    total = round(segs[-1]["end"] + TAIL, 3)
    tl = {"total": total, "segments": segs}
    (V2 / "timeline.json").write_text(json.dumps(tl, indent=1), encoding="utf-8")
    return tl


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def lowpass(x, cutoff):
    return sosfilt(butter(2, cutoff, btype="low", fs=SR, output="sos"), x)


def highpass(x, cutoff):
    return sosfilt(butter(2, cutoff, btype="high", fs=SR, output="sos"), x)


def saw(f, t, detune=0.0):
    ph = (f * (1 + detune)) * t
    return 2 * (ph - np.floor(ph + 0.5))


def env_adsr(n, a, r):
    e = np.ones(n)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


# Am, F, C, G  (voicings as MIDI notes, bass separately)
CHORDS = [([57, 60, 64, 69], 45), ([57, 60, 65, 69], 41), ([55, 60, 64, 67], 48), ([55, 59, 62, 67], 43)]


def render_music(tl: dict) -> Path:
    total = tl["total"]
    n = int(total * SR) + SR
    L, R = np.zeros(n), np.zeros(n)
    seg = {s["id"]: s for s in tl["segments"]}
    bar = 4 * BEAT

    def level(section: str, t: float) -> float:
        """Arrangement: which layers play when (0..1 gain)."""
        gap_s, sol_s, tw_s, tw_e, th_s, cta_s = (seg["gap"]["start"], seg["solution"]["start"], seg["twist"]["start"],
                                                  seg["twist"]["start"] + 4 * BEAT * 2, seg["threed"]["start"], seg["cta"]["start"])
        if section == "pad":
            return 1.0
        if section == "arp":
            return 0.0 if t < gap_s - 0.3 else (0.35 if tw_s <= t < tw_e else 1.0) * (0.6 if t >= cta_s + 2.0 else 1.0)
        if section == "beat":
            return 0.0 if t < sol_s - 0.2 or (tw_s <= t < tw_e) or t >= cta_s + 1.2 else (1.0 if t >= th_s - 0.1 or t < tw_s else 0.8)
        return 1.0

    n_bars = int(np.ceil(total / bar)) + 1
    for b in range(n_bars):
        t0 = b * bar
        notes, bass = CHORDS[b % 4]
        i0, i1 = int(t0 * SR), min(n, int((t0 + bar + 0.6) * SR))
        tt = np.arange(i1 - i0) / SR
        # pad: detuned saws, slow attack, low-passed
        pad = sum(saw(midi(m), tt, d) for m in notes for d in (-0.004, 0.0, 0.0045)) / (len(notes) * 3)
        pad = lowpass(pad * env_adsr(len(tt), 0.9, 0.9), 1400)
        bs = lowpass(saw(midi(bass), tt) * env_adsr(len(tt), 0.05, 0.5), 260)
        g = level("pad", t0)
        L[i0:i1] += 0.16 * g * pad + 0.20 * bs
        R[i0:i1] += 0.16 * g * np.roll(pad, 220) + 0.20 * bs
        # arpeggio: 16th notes over chord tones an octave up, plucked
        arp_notes = [notes[0] + 12, notes[1] + 12, notes[2] + 12, notes[3] + 12, notes[2] + 12, notes[1] + 12, notes[0] + 24, notes[2] + 12]
        for k in range(16):
            ts = t0 + k * BEAT / 4
            ga = level("arp", ts)
            if ga <= 0:
                continue
            j0, ln = int(ts * SR), int(0.34 * SR)
            if j0 + ln >= n:
                continue
            tn = np.arange(ln) / SR
            f = midi(arp_notes[k % 8])
            pl = (np.sin(2 * np.pi * f * tn) + 0.35 * np.sin(4 * np.pi * f * tn)) * np.exp(-tn * 14)
            pan = 0.5 + 0.35 * np.sin(k * 0.9)
            L[j0:j0 + ln] += 0.055 * ga * pl * (1 - pan) * 2
            R[j0:j0 + ln] += 0.055 * ga * pl * pan * 2
        # beat: soft kick on 1 & 3, clap on 2 & 4, closed hats on 8ths
        for k in range(8):
            ts = t0 + k * BEAT / 2
            gb = level("beat", ts)
            if gb <= 0:
                continue
            j0 = int(ts * SR)
            if k % 4 == 0 and j0 + int(0.4 * SR) < n:
                tn = np.arange(int(0.4 * SR)) / SR
                kick = np.sin(2 * np.pi * (48 + 90 * np.exp(-tn * 30)) * tn) * np.exp(-tn * 9)
                L[j0:j0 + len(tn)] += 0.42 * gb * kick
                R[j0:j0 + len(tn)] += 0.42 * gb * kick
            if k % 4 == 2 and j0 + int(0.25 * SR) < n:
                ln = int(0.25 * SR)
                clap = highpass(np.random.default_rng(b * 8 + k).normal(size=ln), 900) * np.exp(-np.arange(ln) / SR * 22)
                L[j0:j0 + ln] += 0.07 * gb * clap
                R[j0:j0 + ln] += 0.07 * gb * clap
            ln = int(0.06 * SR)
            if j0 + ln < n:
                hat = highpass(np.random.default_rng(1000 + b * 8 + k).normal(size=ln), 7000) * np.exp(-np.arange(ln) / SR * 70)
                acc = 1.0 if k % 2 else 0.6
                L[j0:j0 + ln] += 0.05 * gb * acc * hat * 0.8
                R[j0:j0 + ln] += 0.05 * gb * acc * hat * 1.2
    # riser into the twist and into 3D (filtered noise swell)
    for key in ("twist", "threed"):
        te = seg[key]["start"]
        ln = int(1.6 * SR)
        j0 = int((te - 1.6) * SR)
        sw = highpass(np.random.default_rng(7).normal(size=ln), 2500) * np.linspace(0, 1, ln) ** 2
        L[j0:j0 + ln] += 0.05 * sw
        R[j0:j0 + ln] += 0.05 * sw
    # master: fade in/out, gentle limiting
    m = np.stack([L, R], axis=1)[: int(total * SR)]
    fade_in, fade_out = int(1.2 * SR), int(2.2 * SR)
    m[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    m[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
    m = np.tanh(1.6 * m) / np.tanh(1.6)
    m /= np.max(np.abs(m)) / 0.9
    out = V2 / "audio" / "music.wav"
    wavfile.write(out, SR, (m * 32767).astype(np.int16))
    return out


if __name__ == "__main__":
    tl = build_timeline()
    print("timeline total", tl["total"], "s;", ", ".join(f"{s['id']}@{s['start']:.1f}" for s in tl["segments"]))
    print("music ->", render_music(tl))
