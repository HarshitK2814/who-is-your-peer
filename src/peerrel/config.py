"""Paths, YAML configs and the SEC User-Agent (read from the git-ignored .env file)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
RESULTS = ROOT / "results"
RESEARCH = ROOT / "research"


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def sec_user_agent() -> str:
    _load_dotenv()
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise RuntimeError("Set SEC_USER_AGENT='Name email' in .env (SEC fair-access policy).")
    return ua


@lru_cache
def load(name: str) -> dict:
    return yaml.safe_load((ROOT / "configs" / f"{name}.yaml").read_text())


for p in (RAW, INTERIM, PROCESSED, RESULTS / "figures", RESULTS / "tables", RESULTS / "runs"):
    p.mkdir(parents=True, exist_ok=True)
