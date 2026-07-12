#!/usr/bin/env python3
"""Generate Figure 5: Gas consumption comparison (Base vs. Solana).

Input:
  ../daily_gas_fee_trend.csv

Output:
  fig5.pdf
"""

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.dates import AutoDateLocator, DateFormatter
from matplotlib.ticker import FuncFormatter, MaxNLocator

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

DAILY_GAS_CSV = PROJECT_DIR / "daily_gas_fee_trend.csv"
OUTPUT_PDF = SCRIPT_DIR / "fig5.pdf"

ETH_PRICE_USD = 3000
SOL_PRICE_USD = 125
START_DATE = pd.Timestamp("2025-10-01")

BASE_SUCCESS_ETH = 46.542371
BASE_REVERT_ETH = 1.938250
SOL_SUCCESS_SOL = 456.298552
SOL_FAILED_SOL = 0.027700

BASE_COLOR = (135 / 255, 86 / 255, 140 / 255)
SOL_COLOR = (243 / 255, 161 / 255, 125 / 255)
CAPTION_FONT = (
    "Times New Roman"
    if any(f.name == "Times New Roman" for f in font_manager.fontManager.ttflist)
    else "DejaVu Serif"
)


def fmt_usd(x, pos=None):
    ax = abs(x)
    if ax >= 1e6:
        return f"${x / 1e6:.1f}M"
    if ax >= 1e3:
        return f"${x / 1e3:.0f}K"
    if ax >= 1:
        return f"${x:.2f}"
    return f"${x:.3f}"


def require_columns(df: pd.DataFrame, path: Path, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def load_pie_values() -> tuple[list[str], list[float], list[str], list[float]]:
    base_success_usd = BASE_SUCCESS_ETH * ETH_PRICE_USD
    base_revert_usd = BASE_REVERT_ETH * ETH_PRICE_USD
    sol_success_usd = SOL_SUCCESS_SOL * SOL_PRICE_USD
    sol_failed_usd = SOL_FAILED_SOL * SOL_PRICE_USD

    labels = ["Base Success", "Base Revert", "Solana Success", "Solana Revert"]
    values = [base_success_usd, base_revert_usd, sol_success_usd, sol_failed_usd]
    colors = ["#b7d9a8", "#f2b179", "#9ad9f5", "#e5a4a4"]
    explode = [0, 0.12, 0, 0.12]
    return labels, values, colors, explode

def make_pie_labels(labels: list[str], values: list[float]) -> list[str]:
    total = sum(values)
    pie_labels = []
    for name, value in zip(labels, values):
        pct = value / total * 100 if total else 0
        pct_str = "<0.1%" if 0 < pct < 0.1 else f"{pct:.1f}%"
        money = f"${value / 1000:.1f}K" if value >= 1000 else f"${value:.2f}"
        pie_labels.append(f"{name}\n{pct_str}\n{money}")
    return pie_labels


def load_daily_trend() -> pd.DataFrame:
    if not DAILY_GAS_CSV.exists():
        raise FileNotFoundError(
            f"Missing input {DAILY_GAS_CSV}. Run `python daily_gas_fee_trend.py` from the project root first."
        )

    df = pd.read_csv(DAILY_GAS_CSV)
    require_columns(df, DAILY_GAS_CSV, ["day", "base_gasfee_eth", "sol_fee"])

    # day is blocktime DIV 86400, i.e., epoch-day.
    df["day"] = pd.to_datetime(df["day"], unit="D", origin="unix", errors="coerce")
    df = df.dropna(subset=["day"]).sort_values("day")

    df["base_gasfee_eth"] = pd.to_numeric(df["base_gasfee_eth"], errors="coerce").fillna(0)
    df["sol_fee"] = pd.to_numeric(df["sol_fee"], errors="coerce").fillna(0)
    df["base_fee_usd"] = df["base_gasfee_eth"] * ETH_PRICE_USD
    df["sol_fee_usd"] = df["sol_fee"] * SOL_PRICE_USD

    df = df[df["day"] >= START_DATE].copy()
    if df.empty:
        raise ValueError(f"No daily gas rows remain after filtering day >= {START_DATE.date()}")
    return df


def plot_fig5() -> None:
    labels, values, colors, explode = load_pie_values()
    pie_labels = make_pie_labels(labels, values)
    df = load_daily_trend()

    plt.rcParams.update(
        {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 13,
            "axes.labelsize": 16,
            "axes.titlesize": 12,
            "legend.fontsize": 13,
            "xtick.labelsize": 14,
            "ytick.labelsize": 14,
        }
    )

    fig, (ax0, ax1) = plt.subplots(
        1,
        2,
        figsize=(10, 3),
        gridspec_kw={"width_ratios": [1.0, 1.0], "wspace": 0.8},
    )

    # (a) Aggregate gas fee breakdown
    ax0.pie(
        values,
        labels=pie_labels,
        colors=colors,
        explode=explode,
        startangle=90,
        counterclock=False,
        labeldistance=1.3,
        wedgeprops=dict(edgecolor="white", linewidth=1),
    )
    ax0.set_aspect("equal")

    # (b) Daily stacked gas fees
    bar_width = 0.85
    ax1.bar(df["day"], df["base_fee_usd"], width=bar_width, label="Base", color=BASE_COLOR)
    ax1.bar(
        df["day"],
        df["sol_fee_usd"],
        width=bar_width,
        bottom=df["base_fee_usd"],
        label="Solana",
        color=SOL_COLOR,
    )

    ax1.set_ylabel("Daily Gas Fees")
    ax1.grid(True, axis="y", alpha=0.3)
    ax1.legend(loc="upper right", bbox_to_anchor=(1.05, 1), handletextpad=0.4, frameon=False)
    ax1.yaxis.set_major_formatter(FuncFormatter(fmt_usd))

    locator = AutoDateLocator(minticks=3, maxticks=4)
    ax1.xaxis.set_major_locator(locator)
    ax1.xaxis.set_major_formatter(DateFormatter("%b %d"))
    ax1.set_xlabel("Date (2025)")
    ax1.yaxis.set_major_locator(MaxNLocator(nbins=5))

    ax0.text(
        0.5,
        -0.3,
        "(a) Aggregate Gas Fee Breakdown.",
        transform=ax0.transAxes,
        ha="center",
        va="top",
        fontsize=20,
        fontfamily=CAPTION_FONT,
    )
    ax1.text(
        0.5,
        -0.3,
        "(b) Daily Gas Fee Expenditure.",
        transform=ax1.transAxes,
        ha="center",
        va="top",
        fontsize=20,
        fontfamily=CAPTION_FONT,
    )

    fig.tight_layout()
    fig.savefig(OUTPUT_PDF, format="pdf", bbox_inches="tight")
    plt.close(fig)

    print(f"Price assumptions: ETH=${ETH_PRICE_USD}, SOL=${SOL_PRICE_USD}")
    print(
        "Aggregate pie constants:",
        f"Base success={BASE_SUCCESS_ETH} ETH,",
        f"Base revert={BASE_REVERT_ETH} ETH,",
        f"Solana success={SOL_SUCCESS_SOL} SOL,",
        f"Solana failed={SOL_FAILED_SOL} SOL",
    )
    print(
        "Daily rows:",
        len(df),
        "date range:",
        df["day"].min().date(),
        "to",
        df["day"].max().date(),
    )
    print(f"Saved: {OUTPUT_PDF}")


def main() -> None:
    plot_fig5()


if __name__ == "__main__":
    main()
