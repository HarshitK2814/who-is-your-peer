"""Free raw-data downloads: SEC bulk files and the Ken French data library.

All downloads are resumable-by-skip (an existing file is kept), and a manifest with the
source URL, retrieval time, size and sha256 is written next to each file so every result
can be traced back to an exact data vintage.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from peerrel.config import RAW, sec_user_agent

SEC_FILES = {
    "companyfacts.zip": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
    "submissions.zip": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
    "company_tickers_exchange.json": "https://www.sec.gov/files/company_tickers_exchange.json",
}
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRENCH_FILES = [
    "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    "F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "F-F_Momentum_Factor_CSV.zip",
    "F-F_Momentum_Factor_daily_CSV.zip",
    "Siccodes12.zip",
    "Siccodes49.zip",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path, headers: dict | None = None, force: bool = False) -> Path:
    if dest.exists() and not force:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(5):
        try:
            with requests.get(url, headers=headers or {}, stream=True, timeout=120) as r:
                r.raise_for_status()
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            break
        except requests.RequestException as e:
            print(f"retry {attempt + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"failed to download {url}")
    tmp.replace(dest)
    manifest = {"url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "bytes": dest.stat().st_size, "sha256": _sha256(dest)}
    dest.with_suffix(dest.suffix + ".manifest.json").write_text(json.dumps(manifest, indent=2))
    return dest


def download_sec() -> None:
    headers = {"User-Agent": sec_user_agent(), "Accept-Encoding": "gzip, deflate"}
    for name, url in SEC_FILES.items():
        print("SEC", name, flush=True)
        fetch(url, RAW / "sec" / name, headers)


def download_french() -> None:
    for name in FRENCH_FILES:
        fetch(FRENCH + name, RAW / "french" / name)


if __name__ == "__main__":
    (RAW / "sec").mkdir(parents=True, exist_ok=True)
    (RAW / "french").mkdir(parents=True, exist_ok=True)
    download_french()
    download_sec()
    print("done")
