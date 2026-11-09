import pandas as pd

from peerrel.v2.forward_log import append_new, forward_dates, pending_flags
from qcore.splits import Splits


def _rows(dates, book="V0_FF49"):
    return pd.DataFrame({"date": pd.to_datetime(dates), "book": book, "net_return": 0.001, "prereg_hash": "h"})


def test_append_is_idempotent(tmp_path):
    p = tmp_path / "forward.csv"
    assert append_new(p, _rows(["2026-11-30", "2026-12-31"])) == 2
    assert append_new(p, _rows(["2026-11-30", "2026-12-31"])) == 0
    assert append_new(p, _rows(["2026-12-31", "2027-01-31"])) == 1
    df = pd.read_csv(p)
    assert len(df) == 3 and not df.duplicated(["date", "book"]).any()


def test_two_books_same_month_kept(tmp_path):
    p = tmp_path / "f.csv"
    append_new(p, pd.concat([_rows(["2026-11-30"]), _rows(["2026-11-30"], "SIN_FF49")]))
    assert len(pd.read_csv(p)) == 2


def test_forward_window_excludes_seen_months():
    s = Splits.from_dict({"development": ["2012-01", "2016-12"], "validation": ["2017-01", "2019-12"],
                          "test": ["2020-01", "2023-12"], "recent": ["2024-01", "2026-10"], "forward": ["2026-11", None]})
    idx = pd.to_datetime(["2026-09-30", "2026-10-31", "2026-11-30", "2026-12-31"])
    assert forward_dates(idx, s) == list(idx[2:])
    flags = pending_flags(idx[2:], {idx[2]: True})
    assert flags == {idx[2]: False, idx[3]: True}
