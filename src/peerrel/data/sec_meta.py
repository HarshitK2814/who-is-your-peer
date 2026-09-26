"""Company metadata from free SEC files: CIK -> primary ticker, exchange, SIC code.

Limitation (documented in research/limitations.md): the SEC ticker file lists *currently*
traded securities and the SIC code in `submissions.zip` is the *current* code. Neither is
point-in-time. This is the main source of survivorship bias in the free-data design.
"""

from __future__ import annotations

import json
import re
import zipfile

import pandas as pd

from peerrel.config import INTERIM, RAW

MAJOR_EXCHANGES = {"NYSE", "Nasdaq"}
_NON_COMMON = re.compile(r"[-.]|^[A-Z]{4}[WURZ]$")   # preferreds/classes with separators; Nasdaq W/U/R/Z suffixes


def primary_tickers() -> pd.DataFrame:
    d = json.loads((RAW / "sec" / "company_tickers_exchange.json").read_text())
    df = pd.DataFrame(d["data"], columns=d["fields"])
    df["order"] = range(len(df))
    df = df[df["exchange"].isin(MAJOR_EXCHANGES) & ~df["ticker"].str.contains(_NON_COMMON)]
    df = df.sort_values(["cik", "order"]).drop_duplicates("cik", keep="first")
    return df[["cik", "ticker", "exchange", "name"]].reset_index(drop=True)


def sic_codes(ciks: set[int] | None = None) -> pd.DataFrame:
    """Read `sic` for each CIK from submissions.zip (one small JSON per company)."""
    rows = []
    with zipfile.ZipFile(RAW / "sec" / "submissions.zip") as z:
        for name in z.namelist():
            m = re.match(r"CIK(\d{10})\.json$", name)
            if not m:
                continue  # skip paginated "-submissions-001.json" history files
            cik = int(m.group(1))
            if ciks is not None and cik not in ciks:
                continue
            j = json.loads(z.read(name))
            sic = j.get("sic")
            rows.append((cik, int(sic) if sic and str(sic).isdigit() else None,
                         j.get("sicDescription"), j.get("stateOfIncorporation"), j.get("category")))
    return pd.DataFrame(rows, columns=["cik", "sic", "sic_description", "state_of_inc", "filer_category"])


def build_company_table() -> pd.DataFrame:
    tick = primary_tickers()
    sic = sic_codes(set(tick["cik"]))
    out = tick.merge(sic, on="cik", how="left")
    out.to_parquet(INTERIM / "companies.parquet", index=False)
    print(f"{len(out):,} companies with NYSE/Nasdaq primary tickers; SIC missing for {out['sic'].isna().sum()}")
    return out


if __name__ == "__main__":
    build_company_table()
