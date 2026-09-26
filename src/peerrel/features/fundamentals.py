"""Point-in-time fundamental characteristics from as-first-reported XBRL facts.

Pipeline
--------
1. Flows are reported as 3-month, year-to-date (6M/9M) or annual durations. Discrete
   quarters come from 3-month facts directly, or from differencing two facts with the same
   start date that end ~3 months apart (6M-3M, 9M-6M, FY-9M).
2. TTM = sum of four consecutive discrete quarters (or a reported annual value).
3. Every derived number carries `avail` = the latest filing date of any input it used.
4. Characteristics are computed per fiscal period (cik, m), where `m` is an integer month
   key of the period end, and then made point-in-time: at month-end t we use the row with the
   *latest period end among rows whose inputs were all filed before t*.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FLOW_CONCEPTS = ["revenue", "cogs", "gross_profit", "net_income", "cfo", "eps", "equity_issued",
                 "equity_repurchased", "debt_issued", "debt_repaid", "st_debt_net"]
INSTANT_CONCEPTS = ["assets", "liabilities", "liab_and_equity", "equity", "shares_out", "shares_out_bs"]


def month_key(dates: pd.Series) -> pd.Series:
    """Integer month index of a period end; +7 days maps 52/53-week year ends (e.g. Sep 28 or
    Oct 2) consistently onto the calendar month they belong to."""
    d = pd.to_datetime(dates) + pd.Timedelta(days=7)
    return (d.dt.year * 12 + d.dt.month - 1).astype("int64")


def _dedupe(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (df.sort_values(keys + ["avail"]).drop_duplicates(keys, keep="first").reset_index(drop=True))


def discrete_quarters(flows: pd.DataFrame) -> pd.DataFrame:
    """flows: cik, concept, start, end, val, filed (durations only) -> cik, concept, m, val, avail."""
    f = flows.copy()
    f["days"] = (f["end"] - f["start"]).dt.days + 1
    f = f[(f["days"] >= 80) & (f["days"] <= 380)]
    direct = f[f["days"] <= 100][["cik", "concept", "end", "val", "filed"]].rename(columns={"filed": "avail"})
    direct["rank"] = 0
    long = f[f["days"] > 100]
    pairs = long.merge(f, on=["cik", "concept", "start"], suffixes=("", "_g"))
    gap = (pairs["end"] - pairs["end_g"]).dt.days
    pairs = pairs[(gap >= 70) & (gap <= 110)]
    derived = pd.DataFrame({
        "cik": pairs["cik"], "concept": pairs["concept"], "end": pairs["end"],
        "val": pairs["val"] - pairs["val_g"], "avail": pairs[["filed", "filed_g"]].max(axis=1), "rank": 1,
    })
    q = pd.concat([direct, derived], ignore_index=True)
    q["m"] = month_key(q["end"])
    q = q.sort_values(["cik", "concept", "m", "avail", "rank"]).drop_duplicates(["cik", "concept", "m"])
    return q[["cik", "concept", "m", "val", "avail"]].reset_index(drop=True)


def ttm(flows: pd.DataFrame, quarters: pd.DataFrame) -> pd.DataFrame:
    """Trailing-twelve-month sums from four consecutive quarters, plus reported annual values."""
    q = quarters.sort_values(["cik", "concept", "m"]).reset_index(drop=True)
    g = q.groupby(["cik", "concept"], sort=False)
    total, avail, ok = q["val"].copy(), q["avail"].copy(), pd.Series(True, index=q.index)
    for k in (1, 2, 3):
        mk, vk, ak = g["m"].shift(k), g["val"].shift(k), g["avail"].shift(k)
        ok &= (q["m"] - mk) == 3 * k
        total = total + vk
        avail = pd.concat([avail, ak], axis=1).max(axis=1)
    summed = pd.DataFrame({"cik": q["cik"], "concept": q["concept"], "m": q["m"],
                           "val": total, "avail": avail})[ok.fillna(False)]
    f = flows.copy()
    days = (f["end"] - f["start"]).dt.days + 1
    annual = f[(days >= 350) & (days <= 380)]
    annual = pd.DataFrame({"cik": annual["cik"], "concept": annual["concept"],
                           "m": month_key(annual["end"]), "val": annual["val"], "avail": annual["filed"]})
    return _dedupe(pd.concat([annual, summed], ignore_index=True), ["cik", "concept", "m"])


def instants(facts: pd.DataFrame) -> pd.DataFrame:
    i = facts[facts["concept"].isin(INSTANT_CONCEPTS)]
    out = pd.DataFrame({"cik": i["cik"], "concept": i["concept"], "m": month_key(i["end"]),
                        "val": i["val"], "avail": i["filed"]})
    return _dedupe(out, ["cik", "concept", "m"])


def _wide(long: pd.DataFrame, suffix: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    v = long.pivot_table(index=["cik", "m"], columns="concept", values="val", aggfunc="first")
    a = long.pivot_table(index=["cik", "m"], columns="concept", values="avail", aggfunc="first")
    v.columns = [f"{c}{suffix}" for c in v.columns]
    a.columns = [f"{c}{suffix}" for c in a.columns]
    return v, a


def _lag(frame: pd.DataFrame, months: int) -> pd.DataFrame:
    lagged = frame.copy()
    lagged.index = lagged.index.set_levels(lagged.index.levels[1] + months, level="m")
    return lagged.reindex(frame.index)


def _m_to_ts(m: pd.Series) -> pd.DatetimeIndex:
    return pd.to_datetime(pd.DataFrame({"year": m // 12, "month": m % 12 + 1, "day": 1}))


def rolling_quarterly(series: pd.Series, avail: pd.Series, window: str, min_obs: int, func: str,
                      closed: str = "right") -> tuple[pd.Series, pd.Series]:
    """Time-based rolling statistic over a firm's quarterly observations (index: cik, m).
    Using a calendar window (not a row count) means missing quarters shrink the sample
    instead of silently stretching the window back in time."""
    epoch = pd.Timestamp("1970-01-01")
    df = pd.DataFrame({"v": series, "a": (avail - epoch) / pd.Timedelta(days=1)}).dropna()
    if df.empty:
        return pd.Series(dtype=float), pd.Series(dtype="datetime64[ns]")
    df = df.reset_index().sort_values(["cik", "m"]).reset_index(drop=True)
    df["ts"] = _m_to_ts(df["m"]).to_numpy()
    out_v, out_a = [], []
    for _, g in df.groupby("cik", sort=True):
        g = g.set_index("ts")
        out_v.append(getattr(g["v"].rolling(window, min_periods=min_obs, closed=closed), func)().to_numpy())
        out_a.append(g["a"].rolling(window, min_periods=min_obs, closed=closed).max().to_numpy())
    idx = pd.MultiIndex.from_frame(df[["cik", "m"]])
    v = pd.Series(np.concatenate(out_v), index=idx)
    a = epoch + pd.to_timedelta(pd.Series(np.concatenate(out_a), index=idx), unit="D")
    return v, a


def period_characteristics(facts: pd.DataFrame) -> pd.DataFrame:
    """Characteristic values per fiscal period (cik, m) with an `avail_<char>` column each."""
    flows = facts[facts["concept"].isin(FLOW_CONCEPTS) & facts["start"].notna()]
    q = discrete_quarters(flows)
    t = ttm(flows, q)
    ins = instants(facts)
    qv, qa = _wide(q, "_q")
    tv, ta = _wide(t, "_ttm")
    iv, ia = _wide(ins, "")
    idx = qv.index.union(tv.index).union(iv.index)
    V = pd.concat([qv, tv, iv], axis=1).reindex(idx)
    A = pd.concat([qa, ta, ia], axis=1).reindex(idx)
    for c in ["revenue_ttm", "cogs_ttm", "gross_profit_ttm", "net_income_ttm", "cfo_ttm", "equity_issued_ttm",
              "equity_repurchased_ttm", "debt_issued_ttm", "debt_repaid_ttm", "st_debt_net_ttm", "assets",
              "liabilities", "liab_and_equity", "equity", "shares_out", "shares_out_bs", "eps_q", "cfo_q"]:
        if c not in V:
            V[c] = np.nan
            A[c] = pd.NaT

    # fallbacks (value and availability move together)
    gp_missing = V["gross_profit_ttm"].isna()
    V.loc[gp_missing, "gross_profit_ttm"] = V["revenue_ttm"] - V["cogs_ttm"]
    A.loc[gp_missing, "gross_profit_ttm"] = A[["revenue_ttm", "cogs_ttm"]].max(axis=1)
    liab_missing = V["liabilities"].isna()
    V.loc[liab_missing, "liabilities"] = V["liab_and_equity"] - V["equity"]
    A.loc[liab_missing, "liabilities"] = A[["liab_and_equity", "equity"]].max(axis=1)

    V_l4, A_l4 = _lag(V, 12), _lag(A, 12)

    def out(value: pd.Series, *avails: pd.Series) -> tuple[pd.Series, pd.Series]:
        return value, pd.concat(avails, axis=1).max(axis=1, skipna=False)

    avg_assets = (V["assets"] + V_l4["assets"]) / 2
    a_avg = [A["assets"], A_l4["assets"]]
    res: dict[str, tuple[pd.Series, pd.Series]] = {}

    # --- Quality
    res["gp_to_assets"] = out(V["gross_profit_ttm"] / avg_assets, A["gross_profit_ttm"], *a_avg)
    res["accruals_neg"] = out(-(V["net_income_ttm"] - V["cfo_ttm"]) / avg_assets,
                              A["net_income_ttm"], A["cfo_ttm"], *a_avg)
    res["leverage_neg"] = out(-V["liabilities"] / V["assets"], A["liabilities"], A["assets"])
    # 8 quarters = period ends m-21..m; a 690-day window includes m-21 (~640d) and excludes m-24 (~730d)
    cfo_std, cfo_std_avail = rolling_quarterly(V["cfo_q"], A["cfo_q"], "690D", 6, "std")
    res["cf_stability"] = out(-cfo_std.reindex(V.index) / V["assets"], cfo_std_avail.reindex(V.index), A["assets"])

    # --- Management decisions (internal over external funding); missing components count as 0,
    #     but the cash-flow statement itself (CFO) must be present.
    comps = ["equity_issued_ttm", "equity_repurchased_ttm", "debt_issued_ttm", "debt_repaid_ttm", "st_debt_net_ttm"]
    filled = V[comps].fillna(0.0)
    nef = filled["equity_issued_ttm"] - filled["equity_repurchased_ttm"] + filled["debt_issued_ttm"] \
        - filled["debt_repaid_ttm"] + filled["st_debt_net_ttm"]
    nef = nef.where(V["cfo_ttm"].notna())
    res["ext_financing_neg"] = out(-nef / avg_assets, A["cfo_ttm"], *a_avg)
    res["asset_growth_neg"] = out(-(V["assets"] / V_l4["assets"] - 1), *a_avg)

    # --- Growth
    res["sales_growth"] = out(V["revenue_ttm"] / V_l4["revenue_ttm"] - 1, A["revenue_ttm"], A_l4["revenue_ttm"])
    eps_up = (V["eps_q"] > V_l4["eps_q"]).astype(float).where(V["eps_q"].notna() & V_l4["eps_q"].notna())
    eps_avail = pd.concat([A["eps_q"], A_l4["eps_q"]], axis=1).max(axis=1)
    persist, persist_avail = rolling_quarterly(eps_up, eps_avail, "690D", 6, "mean")
    res["eps_persistence"] = out(persist.reindex(V.index), persist_avail.reindex(V.index))

    # --- Sentiment (accounting part): standardised unexpected earnings, seasonal random walk.
    #     Scale = std of the previous 8 quarterly changes (window excludes the current quarter).
    d = V["eps_q"] - V_l4["eps_q"]
    d_std, d_std_avail = rolling_quarterly(d, eps_avail, "780D", 6, "std", closed="left")
    res["sue"] = out(d / d_std.reindex(V.index), eps_avail, d_std_avail.reindex(V.index))

    # --- Levels needed later for valuation ratios and share issuance
    for c in ["net_income_ttm", "cfo_ttm", "revenue_ttm", "equity"]:
        res[c] = out(V[c], A[c])
    shares = V["shares_out"].fillna(V["shares_out_bs"])
    res["shares_out"] = out(shares, A["shares_out"].fillna(A["shares_out_bs"]))

    frame = pd.DataFrame({k: v for k, (v, _) in res.items()})
    for k, (_, a) in res.items():
        frame[f"avail_{k}"] = a
    return frame.replace([np.inf, -np.inf], np.nan)


def point_in_time(period: pd.DataFrame, month_ends: pd.DatetimeIndex, max_age_months: int = 15,
                  with_period: tuple[str, ...] = ()) -> pd.DataFrame:
    """For each month-end t and firm: the latest fiscal period whose value was filed strictly
    before t (a filing becomes usable the day after it is filed). Values older than
    `max_age_months` (period end vs t) are treated as missing. For characteristics listed in
    `with_period`, the chosen period key is returned as column `m_<char>`."""
    chars = [c for c in period.columns if not c.startswith("avail_")]
    grid_m = pd.DataFrame({"date": month_ends})
    frames = []
    for c in chars:
        s = period[[c, f"avail_{c}"]].dropna().reset_index()
        s = s.rename(columns={f"avail_{c}": "avail"})
        s["known"] = s["avail"] + pd.Timedelta(days=1)
        s = s.sort_values(["cik", "known", "m"])
        # a row is only relevant if it advances the latest known period end for that firm
        s = s[s["m"] >= s.groupby("cik")["m"].cummax()].drop_duplicates(["cik", "known"], keep="last")
        s = s.sort_values("known")
        grid = grid_m.merge(pd.DataFrame({"cik": s["cik"].unique()}), how="cross").sort_values("date")
        got = pd.merge_asof(grid, s[["cik", "known", "m", c]], left_on="date", right_on="known",
                            by="cik", direction="backward")
        t_m = got["date"].dt.year * 12 + got["date"].dt.month - 1
        got.loc[(t_m - got["m"]) > max_age_months, c] = np.nan
        cols = [c] + ([f"m_{c}"] if c in with_period else [])
        got[f"m_{c}"] = got["m"].where(got[c].notna())
        frames.append(got.set_index(["date", "cik"])[cols])
    return pd.concat(frames, axis=1).sort_index()
