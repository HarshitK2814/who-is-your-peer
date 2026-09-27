"""Export the monthly series used by the interactive showcase page (docs/index.html) as one JSON blob.

Everything shown on the page is recomputed in the browser from these net monthly excess returns, so the
page cannot show a number that the backtest did not produce. Dates are signal month-ends; each return is
earned over the following month. `mkt` is the Fama-French market excess return for that same following month.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from peerrel.config import RESULTS, ROOT  # noqa: E402
from peerrel.data.french import factors  # noqa: E402

RUNS = {"top1000": "full_main", "top500": "robust_univ500", "cost2x": "robust_cost2x", "nomom": "robust_nomom",
        "themes_top1000": "posthoc_themes", "themes_top500": "posthoc_themes_u500"}


def main() -> None:
    series, dates = {}, None
    for key, tag in RUNS.items():
        d = sorted((RESULTS / "runs").glob(f"*_{tag}"))[-1]
        r = pd.read_parquet(d / "returns.parquet")
        w = r.pivot(index="date", columns="book", values="excess_ret").sort_index()
        dates = w.index if dates is None else dates
        w = w.reindex(dates)
        series[key] = {b.replace(".FF49", "").replace("BT_", ""): [round(float(x), 6) for x in w[b]] for b in w.columns}
    ff = factors()
    mkt = ff["Mkt-RF"].reindex(dates + pd.offsets.MonthEnd(1))
    cov = pd.read_csv(RESULTS / "tables" / "survivorship_coverage.csv")
    out = {
        "dates": [d.strftime("%Y-%m") for d in dates],
        "mkt": [round(float(x), 6) for x in mkt],
        "series": series,
        "coverage": {"years": [int(str(y)[:4]) for y in cov["year_end"]],
                     "normalised": [round(float(x), 4) for x in cov["coverage_normalised"]]},
        "periods": {"full": ["2012-01", "2026-07"], "development": ["2012-01", "2016-12"],
                    "validation": ["2017-01", "2019-12"], "test": ["2020-01", "2023-12"], "recent": ["2024-01", "2026-07"]},
    }
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    blob = json.dumps(out, separators=(",", ":"))
    (docs / "showcase_data.json").write_text(blob, encoding="utf-8")
    blob3d = (docs / "showcase_3d.json").read_text(encoding="utf-8")   # from scripts/build_3d_data.py
    page = (docs / "showcase_template.html").read_text(encoding="utf-8") \
        .replace("/*DATA3D*/", blob3d.replace("</", "<\\/")).replace("/*DATA*/", blob.replace("</", "<\\/"))
    # showcase.html: page body only (the artifact host adds the document skeleton)
    (docs / "showcase.html").write_text(page, encoding="utf-8")
    # index.html: full document for GitHub Pages (Settings -> Pages -> /docs)
    (docs / "index.html").write_text(
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        "<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>\n</head>\n<body>\n"
        + page + "\n</body>\n</html>\n", encoding="utf-8")
    print(f"docs/ written: data {len(blob) / 1024:.0f} KB, {len(out['dates'])} months, runs: {list(series)}")


if __name__ == "__main__":
    main()
