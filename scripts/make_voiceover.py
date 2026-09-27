"""Generate the voiceover (edge-tts neural voice) per segment, with word timings for captions.

Writes video/v2/audio/<id>.mp3 and video/v2/timing.json:
  {segments: [{id, duration, captions: [{text, start, end}]}]}
Caption chunk timings come from the voice's own word-boundary events, so captions stay in sync.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "video" / "v2"
NUM_WORDS = {"2.7": 4, "0.68": 4, "0.15": 4, "0.46": 4}   # spoken as e.g. "zero point six eight"


def caption_word_count(text: str) -> int:
    n = 0
    for w in re.findall(r"[\w'.\-]+", text):
        w = w.strip(".")
        n += NUM_WORDS.get(w, 1) if w else 0
    return n


async def synth(seg: dict, voice: str, rate: str) -> dict:
    out = V2 / "audio" / f"{seg['id']}.mp3"
    comm = edge_tts.Communicate(seg["say"], voice, rate=rate, boundary="WordBoundary")
    words, audio = [], bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            words.append({"text": chunk["text"], "start": chunk["offset"] / 1e7, "end": (chunk["offset"] + chunk["duration"]) / 1e7})
    out.write_bytes(bytes(audio))
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout)
    caps, k = [], 0
    for text in seg["captions"]:
        n = caption_word_count(text)
        chunk = words[k:k + n] or words[-1:]
        caps.append({"text": text, "start": round(chunk[0]["start"], 3), "end": round(chunk[-1]["end"], 3)})
        k += n
    return {"id": seg["id"], "duration": round(dur, 3), "n_words": len(words), "captions": caps}


async def main() -> None:
    script = json.loads((V2 / "script.json").read_text(encoding="utf-8"))
    (V2 / "audio").mkdir(parents=True, exist_ok=True)
    res = [await synth(s, script["voice"], script["rate"]) for s in script["segments"]]
    (V2 / "timing.json").write_text(json.dumps({"segments": res}, indent=1), encoding="utf-8")
    for r in res:
        print(f"{r['id']:9s} {r['duration']:5.2f}s  words={r['n_words']}  " + " | ".join(f"{c['start']:.1f}-{c['end']:.1f}" for c in r["captions"]))
    print("total voice", round(sum(r["duration"] for r in res), 1), "s")


if __name__ == "__main__":
    asyncio.run(main())
