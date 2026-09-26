"""Parse SEC `companyfacts.zip` into a long table of *as-first-reported* XBRL facts.

Only the tags needed for the five themes are kept. For every (cik, concept, start, end)
we keep the value from the **earliest filing** that reported it: later restatements and
prior-year comparatives in later filings are ignored, so a value is never "known" before
the date it first became public (`filed`).
"""

from __future__ import annotations

import json
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from peerrel.config import INTERIM, RAW

# concept -> (taxonomy, candidate tags in priority order, unit)
CONCEPTS: dict[str, tuple[str, list[str], str]] = {
    # durations (flows)
    "revenue": ("us-gaap", ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                            "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax",
                            "SalesRevenueGoodsNet"], "USD"),
    "cogs": ("us-gaap", ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold",
                         "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"], "USD"),
    "gross_profit": ("us-gaap", ["GrossProfit"], "USD"),
    "net_income": ("us-gaap", ["NetIncomeLoss", "ProfitLoss"], "USD"),
    "cfo": ("us-gaap", ["NetCashProvidedByUsedInOperatingActivities",
                        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"], "USD"),
    "eps": ("us-gaap", ["EarningsPerShareDiluted", "EarningsPerShareBasic",
                        "EarningsPerShareBasicAndDiluted"], "USD/shares"),
    "equity_issued": ("us-gaap", ["ProceedsFromIssuanceOfCommonStock"], "USD"),
    "equity_repurchased": ("us-gaap", ["PaymentsForRepurchaseOfCommonStock"], "USD"),
    "debt_issued": ("us-gaap", ["ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromIssuanceOfDebt"], "USD"),
    "debt_repaid": ("us-gaap", ["RepaymentsOfLongTermDebt", "RepaymentsOfDebt"], "USD"),
    "st_debt_net": ("us-gaap", ["ProceedsFromRepaymentsOfShortTermDebt"], "USD"),
    # instants (stocks)
    "assets": ("us-gaap", ["Assets"], "USD"),
    "liabilities": ("us-gaap", ["Liabilities"], "USD"),
    "liab_and_equity": ("us-gaap", ["LiabilitiesAndStockholdersEquity"], "USD"),
    "equity": ("us-gaap", ["StockholdersEquity",
                           "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], "USD"),
    "shares_out": ("dei", ["EntityCommonStockSharesOutstanding"], "shares"),
    "shares_out_bs": ("us-gaap", ["CommonStockSharesOutstanding"], "shares"),
}
FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT", "10-QT"}
COLUMNS = ["cik", "concept", "priority", "start", "end", "val", "filed", "form", "accn", "fy", "fp"]


def parse_company(payload: dict) -> pd.DataFrame:
    rows = []
    facts = payload.get("facts", {})
    cik = int(payload.get("cik", 0))
    for concept, (tax, tags, unit) in CONCEPTS.items():
        block = facts.get(tax, {})
        for prio, tag in enumerate(tags):
            for f in block.get(tag, {}).get("units", {}).get(unit, []):
                if f.get("form") not in FORMS:
                    continue
                rows.append((cik, concept, prio, f.get("start"), f["end"], f["val"], f["filed"],
                             f["form"], f["accn"], f.get("fy"), f.get("fp")))
    return pd.DataFrame(rows, columns=COLUMNS)


def first_reported(df: pd.DataFrame) -> pd.DataFrame:
    """Keep, per (cik, concept, start, end), the earliest-filed value; ties -> preferred tag."""
    if df.empty:
        return df
    df = df.copy()
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    df["filed"] = pd.to_datetime(df["filed"])
    df = df.sort_values(["cik", "concept", "start", "end", "filed", "priority"])
    return df.drop_duplicates(["cik", "concept", "start", "end"], keep="first").reset_index(drop=True)


def _process_member(args: tuple[str, list[str]]) -> pd.DataFrame:
    zip_path, names = args
    out = []
    with zipfile.ZipFile(zip_path) as z:
        for name in names:
            try:
                payload = json.loads(z.read(name))
            except (json.JSONDecodeError, KeyError):
                continue
            df = parse_company(payload)
            if not df.empty:
                out.append(first_reported(df))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=COLUMNS)


def build_facts(zip_path: Path = RAW / "sec" / "companyfacts.zip", workers: int = 8,
                chunk: int = 400) -> Path:
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.endswith(".json")]
    tasks = [(str(zip_path), names[i:i + chunk]) for i in range(0, len(names), chunk)]
    parts = []
    with ProcessPoolExecutor(workers) as ex:
        for i, part in enumerate(ex.map(_process_member, tasks), 1):
            parts.append(part)
            print(f"\rparsed {min(i * chunk, len(names))}/{len(names)} companies", end="", flush=True)
    facts = pd.concat(parts, ignore_index=True)
    facts["fy"] = pd.to_numeric(facts["fy"], errors="coerce").astype("Int64")
    out = INTERIM / "xbrl_facts.parquet"
    facts.to_parquet(out, index=False)
    print(f"\nwrote {len(facts):,} facts for {facts['cik'].nunique():,} companies -> {out}")
    return out


if __name__ == "__main__":
    build_facts()
