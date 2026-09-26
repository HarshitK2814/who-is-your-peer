"""Ken French data library: factor returns and SIC -> industry maps (all free)."""

from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from peerrel.config import RAW

FR = RAW / "french"


def _read_first_table(zip_name: str, date_len: int) -> pd.DataFrame:
    """Return the first table in a French CSV (monthly or daily), values converted from % to decimals."""
    with zipfile.ZipFile(FR / zip_name) as z:
        text = z.read(z.namelist()[0]).decode("latin1")
    lines = text.splitlines()
    header_i = next(i for i, l in enumerate(lines) if re.match(r"^\s*,", l))
    rows = []
    for l in lines[header_i + 1:]:
        cell = l.split(",")[0].strip()
        if not (cell.isdigit() and len(cell) == date_len):
            break
        rows.append(l)
    df = pd.read_csv(io.StringIO("\n".join([lines[header_i]] + rows)))
    df = df.rename(columns={df.columns[0]: "date"})
    df.columns = [c.strip() for c in df.columns]
    fmt = "%Y%m" if date_len == 6 else "%Y%m%d"
    df["date"] = pd.to_datetime(df["date"].astype(str), format=fmt)
    if date_len == 6:
        df["date"] = df["date"] + pd.offsets.MonthEnd(0)
    return df.set_index("date").astype(float) / 100.0


def factors(daily: bool = False) -> pd.DataFrame:
    """FF5 + momentum (UMD) + RF, decimals."""
    if daily:
        f5 = _read_first_table("F-F_Research_Data_5_Factors_2x3_daily_CSV.zip", 8)
        mom = _read_first_table("F-F_Momentum_Factor_daily_CSV.zip", 8)
    else:
        f5 = _read_first_table("F-F_Research_Data_5_Factors_2x3_CSV.zip", 6)
        mom = _read_first_table("F-F_Momentum_Factor_CSV.zip", 6)
    mom.columns = ["UMD"]
    return f5.join(mom, how="inner")


def sic_map(n: int) -> pd.DataFrame:
    """Parse SiccodesNN.txt into (lo, hi, industry_id, short_name) ranges."""
    with zipfile.ZipFile(FR / f"Siccodes{n}.zip") as z:
        text = z.read(z.namelist()[0]).decode("latin1")
    rows, current = [], None
    for line in text.splitlines():
        head = re.match(r"^\s*(\d+)\s+(\S+)\s", line)
        rng = re.match(r"^\s+(\d{4})-(\d{4})", line)
        if rng and current:
            rows.append((int(rng.group(1)), int(rng.group(2)), *current))
        elif head:
            current = (int(head.group(1)), head.group(2))
    return pd.DataFrame(rows, columns=["lo", "hi", "industry", "name"])


def assign_industry(sic: pd.Series, n: int) -> pd.Series:
    """Map SIC codes to Fama-French n-industry ids; unmatched codes go to the 'Other' industry (id n)."""
    table = sic_map(n)
    out = pd.Series(n, index=sic.index, dtype="Int64")
    for lo, hi, ind, _ in table.itertuples(index=False):
        out[(sic >= lo) & (sic <= hi)] = ind
    return out.where(sic.notna())
