#!/usr/bin/env python3
"""Generate Figure 4: Top-10 facilitators by volume.

Output:
  fig4.pdf
"""

import re
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter, MaxNLocator

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_PDF = SCRIPT_DIR / "fig4.pdf"

RAW = [
    {"facilitator": "Coinbase",   "tx": "77.17M",  "vol": "$26.85M"},
    {"facilitator": "PayAI",      "tx": "32.99M",  "vol": "$4.58M"},
    {"facilitator": "Dexter",     "tx": "24.08M",  "vol": "$4.62M"},
    {"facilitator": "Daydreams",  "tx": "11.82M",  "vol": "$2.76M"},
    {"facilitator": "Heurist",    "tx": "7.95M",   "vol": "$30.04K"},
    {"facilitator": "X402rs",     "tx": "698.44K", "vol": "$1.50M"},
    {"facilitator": "OpenX402",   "tx": "697.35K", "vol": "$179.78K"},
    {"facilitator": "Anyspend",   "tx": "496.62K", "vol": "$100.07K"},
    {"facilitator": "Codenut",    "tx": "477.92K", "vol": "$110.04K"},
    {"facilitator": "Thirdweb",   "tx": "208.29K", "vol": "$116.16K"},
    {"facilitator": "Corbits",    "tx": "153.62K", "vol": "$616.42"},
    {"facilitator": "Meridian",   "tx": "20.85K",  "vol": "$1.14M"},
    {"facilitator": "X402 Jobs",  "tx": "18.91K",  "vol": "$2.22K"},
    {"facilitator": "Mogami",     "tx": "17.84K",  "vol": "$305.26K"},
    {"facilitator": "Ultravioletadao", "tx": "4.76K", "vol": "$333.20"},
    {"facilitator": "Xecho",      "tx": "4.38K",   "vol": "$422.05"},
    {"facilitator": "Treasure",   "tx": "884",     "vol": "$248.70"},
]

CAPTION_FONT = (
    "Times New Roman"
    if any(f.name == "Times New Roman" for f in font_manager.fontManager.ttflist)
    else "DejaVu Serif"
)


def parse_si(s: str) -> float:
    s = str(s).strip()
    m = re.match(r"^([0-9]*\.?[0-9]+)\s*([KMB])?$", s, re.IGNORECASE)
    if not m:
        raise ValueError(f"Cannot parse SI number: {s}")
    val = float(m.group(1))
    suf = (m.group(2) or "").upper()
    mul = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[suf]
    return val * mul


def parse_usd(s: str) -> float:
    return parse_si(str(s).replace("$", "").replace(",", "").strip())


def fmt_km(x, pos=None):
    ax = abs(x)
    if ax >= 1e9:
        return f"{x / 1e9:.1f}B"
    if ax >= 1e6:
        return f"{x / 1e6:.1f}M"
    if ax >= 1e3:
        return f"{x / 1e3:.0f}K"
    return f"{x:.0f}"


def fmt_usd_km(x, pos=None):
    ax = abs(x)
    if ax >= 1e9:
        return f"${x / 1e9:.1f}B"
    if ax >= 1e6:
        return f"${x / 1e6:.1f}M"
    if ax >= 1e3:
        return f"${x / 1e3:.0f}K"
    return f"${x:.0f}"


def load_x402scan_aligned_data() -> pd.DataFrame:
    df = pd.DataFrame(RAW)
    df["tx_num"] = df["tx"].apply(parse_si)
    df["vol_usd"] = df["vol"].apply(parse_usd)
    return df


def plot_top10_dual_axis(df: pd.DataFrame, rank_by: str = "vol") -> None:
    assert rank_by in ("vol", "tx")
    sort_col = "vol_usd" if rank_by == "vol" else "tx_num"
    top = df.sort_values(sort_col, ascending=False).head(10).copy()

    tx_color = (31 / 255, 119 / 255, 180 / 255)
    vol_color = (243 / 255, 161 / 255, 125 / 255)

    plt.rcParams.update(
        {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 13,
            "axes.labelsize": 16,
            "axes.titlesize": 13,
            "legend.fontsize": 14,
            "xtick.labelsize": 14,
            "ytick.labelsize": 14,
        }
    )

    fig, ax_l = plt.subplots(figsize=(10, 3))
    ax_r = ax_l.twinx()

    x = list(range(len(top)))
    w = 0.42

    ax_l.bar(
        [i - w / 2 for i in x],
        top["tx_num"],
        width=w,
        color=tx_color,
        hatch="//",
        edgecolor="white",
        linewidth=0.8,
        label="Transactions",
    )
    ax_r.bar(
        [i + w / 2 for i in x],
        top["vol_usd"],
        width=w,
        color=vol_color,
        hatch="\\\\",
        edgecolor="white",
        linewidth=0.8,
        label="Volume",
    )

    ax_l.set_ylabel("Transactions")
    ax_r.set_ylabel("Volume")
    ax_l.yaxis.set_major_formatter(FuncFormatter(fmt_km))
    ax_r.yaxis.set_major_formatter(FuncFormatter(fmt_usd_km))
    ax_l.yaxis.set_major_locator(MaxNLocator(nbins=5))
    ax_r.yaxis.set_major_locator(MaxNLocator(nbins=5))

    ax_l.yaxis.label.set_color(tx_color)
    ax_l.tick_params(axis="y", colors=tx_color)
    ax_r.yaxis.label.set_color(vol_color)
    ax_r.tick_params(axis="y", colors=vol_color)

    ax_l.set_xticks(x)
    ax_l.set_xticklabels(top["facilitator"], rotation=25, ha="right")
    ax_l.grid(True, axis="y", alpha=0.3)

    h1, l1 = ax_l.get_legend_handles_labels()
    h2, l2 = ax_r.get_legend_handles_labels()
    ax_l.legend(h1 + h2, l1 + l2, frameon=False, loc="upper right")

    fig.text(
        0.5,
        -0.02,
        "Top-10 Facilitators by Volume.",
        ha="center",
        va="top",
        fontsize=18,
        fontfamily=CAPTION_FONT,
    )

    fig.tight_layout()
    fig.savefig(OUTPUT_PDF, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {OUTPUT_PDF}")
    print("Ranked facilitators:", ", ".join(top["facilitator"]))


def main() -> None:
    df = load_x402scan_aligned_data()
    plot_top10_dual_axis(df, rank_by="vol")


if __name__ == "__main__":
    main()
