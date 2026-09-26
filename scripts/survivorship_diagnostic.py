"""Quantify survivorship bias of the free-data universe.

For each year-end: among ALL companies that reported total assets >= $1bn in a 10-K/10-Q filed
in the previous 15 months (from the full SEC companyfacts file, which includes firms that later
delisted), what fraction appear in our priced universe (current NYSE/Nasdaq tickers with Yahoo data)?
Financials (SIC 6000-6999) are excluded where the SIC is known.
"""

from __future__ import annotations

import json
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from peerrel.config import INTERIM, RAW, RESULTS  # noqa: E402


def _assets(args):
    path, names = args
    rows = []
    with zipfile.ZipFile(path) as z:
        for n in names:
            try:
                j = json.loads(z.read(n))
            except Exception:
                continue
            for f in j.get("facts", {}).get("us-gaap", {}).get("Assets", {}).get("units", {}).get("USD", []):
                if f.get("form") in ("10-K", "10-Q"):
                    rows.append((int(j.get("cik", 0)), f["end"], f["filed"], f["val"]))
    return rows


def main() -> None:
    path = RAW / "sec" / "companyfacts.zip"
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.endswith(".json")]
    tasks = [(str(path), names[i:i + 500]) for i in range(0, len(names), 500)]
    rows = []
    with ProcessPoolExecutor(4) as ex:
        for r in ex.map(_assets, tasks):
            rows += r
    a = pd.DataFrame(rows, columns=["cik", "end", "filed", "assets"])
    a["filed"] = pd.to_datetime(a["filed"])
    from peerrel.data.sec_meta import sic_codes
    sic_all = sic_codes(set(a.loc[a["assets"] >= 1e9, "cik"]))
    comp = sic_all
    panel = pd.read_parquet(INTERIM.parent / "processed" / "panel.parquet", columns=["mcap"])
    fin = set(comp.loc[comp["sic"].between(6000, 6999), "cik"])
    out = []
    for y in range(2011, 2026):
        t = pd.Timestamp(f"{y}-12-31")
        recent = a[(a["filed"] <= t) & (a["filed"] > t - pd.DateOffset(months=15))]
        big = set(recent.loc[recent["assets"] >= 1e9, "cik"]) - fin
        priced = set(panel.loc[t].index[panel.loc[t]["mcap"].notna()]) if t in panel.index.get_level_values(0) else set()
        out.append({"year_end": t.date(), "sec_filers_assets_ge_1bn": len(big),
                    "in_priced_universe": len(big & priced),
                    "coverage": len(big & priced) / max(len(big), 1)})
    df = pd.DataFrame(out)
    # the denominator still contains large filers without listed common stock (debt-only issuers,
    # subsidiaries). Normalising by the latest year's coverage (when ~all listed firms are present)
    # gives an approximate share of the then-listed universe that survives into our data.
    df["coverage_normalised"] = df["coverage"] / df["coverage"].iloc[-1]
    df.to_csv(RESULTS / "tables" / "survivorship_coverage.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
