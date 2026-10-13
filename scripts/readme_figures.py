"""Clean headline figures for the README, from docs/showcase_data.json (monthly net returns of every book)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "results" / "figures"
INK, MUTED, GRID = "#1f2328", "#6e7781", "#d8dee4"
BLUE, ORANGE, GREEN, GREY = "#2f6fdf", "#e07b00", "#1a7f37", "#8c959f"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "figure.dpi": 150})


def load():
    d = json.loads((ROOT / "docs" / "showcase_data.json").read_text())
    idx = pd.PeriodIndex(d["dates"], freq="M").to_timestamp("M")
    s = pd.DataFrame({k: v for k, v in d["series"]["top1000"].items()}, index=idx).astype(float)
    return s, d["periods"]


def shade(ax, periods):
    for name, c in (("validation", "#f6f8fa"), ("test", "#fff8c5"), ("recent", "#f6f8fa")):
        a, b = periods[name]
        ax.axvspan(pd.Period(a).to_timestamp(), pd.Period(b).to_timestamp("M"), color=c, zorder=0)
        ax.text(pd.Period(a).to_timestamp(), 1.0, f" {name}", transform=ax.get_xaxis_transform(), va="top",
                fontsize=8, color=MUTED)


def main():
    s, periods = load()
    fig, ax = plt.subplots(figsize=(9, 4.2))
    shade(ax, periods)
    for k, c, lab in (("B_FF49", ORANGE, "Industry bets (between-peer book)"),
                      ("W_FF49", BLUE, "Stock picks within industries"),
                      ("C_FF49", GREY, "Full composite")):
        ax.plot((1 + s[k].fillna(0)).cumprod(), color=c, lw=1.7, label=lab)
    ax.axhline(1, color=INK, lw=0.6)
    ax.set_ylabel("Growth of $1, net of costs")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Do sector bets add value? Beta-neutral books, Fama-French 49 peers", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "readme_hero.png")
    plt.close(fig)

    # Test-period Sharpe of the industry-bet book under each peer definition
    a, b = periods["test"]
    t = s.loc[pd.Period(a).to_timestamp("M"):pd.Period(b).to_timestamp("M")]
    sh = lambda x: x.mean() / x.std() * np.sqrt(12)
    names = ["FF12", "FF49", "SIC3", "RCLUST"]
    vals = {"Industry bets": [sh(t[f"B_{n}"]) for n in names], "Within industries": [sh(t[f"W_{n}"]) for n in names],
            "Composite": [sh(t[f"C_{n}"]) for n in names]}
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(names))
    for i, (lab, v) in enumerate(vals.items()):
        ax.bar(x + (i - 1) * 0.27, v, 0.27, color=[ORANGE, BLUE, GREY][i], label=lab)
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xticks(x, ["Fama-French 12", "Fama-French 49", "SIC 3-digit", "Return clusters"])
    ax.set_ylabel("Net Sharpe, test 2020-23")
    ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("Same result under every peer definition", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "readme_peers.png")
    plt.close(fig)
    print({k: [round(z, 2) for z in v] for k, v in vals.items()})


if __name__ == "__main__":
    main()
