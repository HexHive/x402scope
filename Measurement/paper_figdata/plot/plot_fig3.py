#!/usr/bin/env python3
"""Generate Figure 3: Growth of x402 transaction activity and volume.

Input:
  ../trend_daily.csv

Output:
  fig3.pdf
"""

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.dates import AutoDateLocator, DateFormatter
from matplotlib.ticker import FuncFormatter, MaxNLocator


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

INPUT_CSV = PROJECT_DIR / "trend_daily.csv"
OUTPUT_PDF = SCRIPT_DIR / "fig3.pdf"

START_DATE = pd.Timestamp("2025-10-01")

BASE_COLOR = (135 / 255, 86 / 255, 140 / 255)
SOL_COLOR = (243 / 255, 161 / 255, 125 / 255)
CAPTION_FONT = "Times New Roman" if any(f.name == "Times New Roman" for f in font_manager.fontManager.ttflist) else "DejaVu Serif"

REQUIRED_COLUMNS = [
    "day",
    "base_tx_cnt",
    "base_usdc_volume",
    "sol_tx_cnt",
    "sol_usdc_volume",
]


def fmt_km(x, pos=None):
    """Format counts with compact K/M/B suffixes."""
    ax = abs(x)
    if ax >= 1e9:
        return f"{x / 1e9:.1f}B"
    if ax >= 1e6:
        return f"{x / 1e6:.1f}M"
    if ax >= 1e3:
        return f"{x / 1e3:.0f}K"
    return f"{x:.0f}"


def fmt_usd_km(x, pos=None):
    """Format USDC volume with compact dollar suffixes."""
    ax = abs(x)
    if ax >= 1e9:
        return f"${x / 1e9:.1f}B"
    if ax >= 1e6:
        return f"${x / 1e6:.1f}M"
    if ax >= 1e3:
        return f"${x / 1e3:.0f}K"
    return f"${x:.0f}"


def load_and_prepare() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Missing input {INPUT_CSV}. Run `python transaction_activity.py` "
            "from the project root first."
        )

    df = pd.read_csv(INPUT_CSV)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{INPUT_CSV} is missing required columns: {missing}")

    # Convert epoch-day to UTC calendar date. The source day is blocktime DIV 86400.
    df["day"] = pd.to_datetime(df["day"], unit="D", origin="unix", errors="coerce")
    df = df.dropna(subset=["day"]).sort_values("day")

    for c in ["base_tx_cnt", "sol_tx_cnt", "base_usdc_volume", "sol_usdc_volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df = df[df["day"] >= START_DATE].copy()
    if df.empty:
        raise ValueError(f"No data remains after filtering day >= {START_DATE.date()}")
    return df


def plot_fig3(df: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 13,
            "axes.labelsize": 16,
            "axes.titlesize": 12,
            "legend.fontsize": 14,
            "xtick.labelsize": 14,
            "ytick.labelsize": 14,
        }
    )

    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(10, 4), sharex=True)
    bar_width = 0.85

    # (a) Daily transactions
    ax = axes[0]
    ax.bar(df["day"], df["base_tx_cnt"], width=bar_width, label="Base", color=BASE_COLOR)
    ax.bar(
        df["day"],
        df["sol_tx_cnt"],
        width=bar_width,
        bottom=df["base_tx_cnt"],
        label="Solana",
        color=SOL_COLOR,
    )
    ax.set_ylabel("Daily Transactions")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(frameon=False)
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_km))

    # (b) Daily USDC volume
    ax = axes[1]
    ax.bar(df["day"], df["base_usdc_volume"], width=bar_width, label="Base", color=BASE_COLOR)
    ax.bar(
        df["day"],
        df["sol_usdc_volume"],
        width=bar_width,
        bottom=df["base_usdc_volume"],
        label="Solana",
        color=SOL_COLOR,
    )
    ax.set_ylabel("Daily USDC Volume")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(frameon=False)
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_usd_km))

    locator = AutoDateLocator(minticks=3, maxticks=4)
    formatter = DateFormatter("%b %d")

    for ax in axes:
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        ax.set_xlabel("Date (2025)")
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        for label in ax.get_xticklabels():
            label.set_rotation(0)
            label.set_horizontalalignment("center")

    axes[0].text(
        0.5,
        -0.3,
        "(a) Daily Transactions.",
        transform=axes[0].transAxes,
        ha="center",
        va="top",
        fontsize=20,
        fontfamily=CAPTION_FONT,
    )
    axes[1].text(
        0.5,
        -0.3,
        "(b) Daily USDC Volume.",
        transform=axes[1].transAxes,
        ha="center",
        va="top",
        fontsize=20,
        fontfamily=CAPTION_FONT,
    )

    fig.tight_layout()
    fig.savefig(OUTPUT_PDF, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {OUTPUT_PDF}")


def main() -> None:
    df = load_and_prepare()
    print(
        "Plotting rows:",
        len(df),
        "date range:",
        df["day"].min().date(),
        "to",
        df["day"].max().date(),
    )
    plot_fig3(df)


if __name__ == "__main__":
    main()
