#!/usr/bin/env python3
"""Generate Figure 6: Revert reason distribution.

Inputs:
  ../base_revert_breakdown.csv
  ../solana_fail_breakdown.csv

Output:
  fig6.pdf
"""

from pathlib import Path
import textwrap

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

BASE_CSV = PROJECT_DIR / "base_revert_breakdown.csv"
SOL_CSV = PROJECT_DIR / "solana_fail_breakdown.csv"
OUTPUT_PDF = SCRIPT_DIR / "fig6.pdf"

TOPK = 3
COLORS = ["#b7d9a8", "#9ad9f5", "#f2b179", "#c9cbe2", "#d4d4d4", "#ff9999", "#ffff99"]
CAPTION_FONT = (
    "Times New Roman"
    if any(f.name == "Times New Roman" for f in font_manager.fontManager.ttflist)
    else "DejaVu Serif"
)


BASE_LABEL_MAP = {
    "execution reverted/FiatTokenV2: authorization is used or canceled": "Authorization is used or canceled.",
    "execution reverted/ERC20: transfer amount exceeds balance": "Transfer amount exceeds balance.",
    "execution reverted/FiatTokenV2: authorization is expired": "Authorization is expired.",
    "execution reverted/FiatTokenV2: invalid signature": "Invalid signature.",
    "execution reverted/": "Unknown revert.",
    "Unknown": "Unknown revert.",
}

SOL_LABEL_MAP = {
    "owner not match": "Owner mismatch.",
    "insufficient funds": "Insufficient funds.",
    "token invalid account data": "Token invalid account data.",
    "ata owner not allowed": "ATA owner not allowed.",
    "rent insufficient": "Rent insufficient.",
    "InsufficientFundsForRent": "Insufficient funds for rent.",
    "Unknown": "Unknown failure.",
}


def require_columns(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def clean_reason(reason: str, mapping: dict[str, str]) -> str:
    reason = str(reason).strip()
    if reason in mapping:
        return mapping[reason]

    for prefix in ["execution reverted/FiatTokenV2: ", "execution reverted/ERC20: ", "execution reverted/"]:
        if reason.startswith(prefix):
            reason = reason[len(prefix):].strip()
            break
    if not reason:
        return "Unknown."
    return reason[:1].upper() + reason[1:] + ("" if reason.endswith(".") else ".")


def topk_plus_other(df: pd.DataFrame, topk: int = TOPK) -> pd.DataFrame:
    d = df.sort_values("cnt", ascending=False).reset_index(drop=True)
    if len(d) <= topk:
        return d
    top = d.head(topk).copy()
    other_cnt = d.loc[topk:, "cnt"].sum()
    other = pd.DataFrame([{"reason": "Other.", "cnt": other_cnt}])
    return pd.concat([top, other], ignore_index=True)


def load_breakdown(path: Path, mapping: dict[str, str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing input {path}. Run `python revert_statistics.py` first.")
    df = pd.read_csv(path)
    require_columns(df, path, ["reason", "cnt"])
    df["cnt"] = pd.to_numeric(df["cnt"], errors="coerce").fillna(0)
    df["reason"] = df["reason"].apply(lambda s: clean_reason(s, mapping))

    # Merge rows that map to the same cleaned label.
    df = df.groupby("reason", as_index=False)["cnt"].sum()
    df = topk_plus_other(df, TOPK)
    total = df["cnt"].sum()
    df["pct"] = df["cnt"] / total * 100 if total else 0
    df["legend_label"] = df["reason"].apply(lambda s: textwrap.fill(str(s), width=28))
    return df


def pie_percent_labels(values: np.ndarray) -> list[str]:
    """One-decimal labels; make the final slice absorb rounding residual."""
    if values.sum() <= 0:
        return ["0.0%"] * len(values)
    pcts = values / values.sum() * 100
    labels = []
    shown = 0.0
    for i, pct in enumerate(pcts):
        if i == len(pcts) - 1:
            val = max(0.0, round(100.0 - shown, 1))
        else:
            val = round(float(pct), 1)
            shown += val
        labels.append(f"{val:.1f}%")
    return labels


def plot_pie(ax, df: pd.DataFrame) -> None:
    vals = df["cnt"].to_numpy(dtype=float)
    colors = (COLORS * (len(vals) // len(COLORS) + 1))[: len(vals)]
    pct_labels = pie_percent_labels(vals)

    wedges, _ = ax.pie(
        vals,
        labels=None,
        colors=colors,
        startangle=80,
        counterclock=False,
        explode=[0] * len(vals),
    )

    for wedge, val in zip(wedges, vals):
        pct = 100.0 * val / vals.sum() if vals.sum() else 0.0
        wedge.set_edgecolor("white")
        wedge.set_linewidth(0.2 if pct < 1.0 else 0.8)

    # Place large percentages inside and small slices outside with leader lines.
    outside = []
    for wedge, txt in zip(wedges, pct_labels):
        pct_val = float(txt.rstrip("%"))
        if pct_val < 0.5:
            continue
        ang = (wedge.theta1 + wedge.theta2) / 2.0
        ang_rad = np.deg2rad(ang)
        x, y = np.cos(ang_rad), np.sin(ang_rad)
        wedge_angle = wedge.theta2 - wedge.theta1
        if wedge_angle >= 18 and pct_val >= 3.0:
            ax.text(0.70 * x, 0.70 * y, txt, ha="center", va="center", fontsize=13)
        else:
            outside.append((y, x, txt))

    def draw_outside(group, side: str) -> None:
        if not group:
            return
        group.sort(key=lambda t: t[0])
        min_dy = 0.18
        ys = [t[0] for t in group]
        for j in range(1, len(ys)):
            if ys[j] - ys[j - 1] < min_dy:
                ys[j] = ys[j - 1] + min_dy
        if len(ys) >= 2:
            ys = np.linspace(ys[0], ys[-1], len(ys))
        for new_y, (old_y, x, txt) in zip(ys, group):
            ha = "left" if side == "right" else "right"
            x_text = 0.5 * (1 if side == "right" else -1)
            ax.annotate(
                txt,
                xy=(0.95 * x, 0.95 * old_y),
                xytext=(x_text, new_y),
                ha=ha,
                va="center",
                fontsize=13,
                arrowprops=dict(arrowstyle="-", lw=0.8),
            )

    draw_outside([t for t in outside if t[1] < 0], "left")
    draw_outside([t for t in outside if t[1] >= 0], "right")

    ax.legend(
        wedges,
        df["legend_label"].tolist(),
        loc="upper center",
        bbox_to_anchor=(0.5, 0.08),
        ncol=1,
        frameon=False,
        fontsize=13,
        handlelength=1.0,
        labelspacing=0.6,
    )


def main() -> None:
    base_df = load_breakdown(BASE_CSV, BASE_LABEL_MAP)
    sol_df = load_breakdown(SOL_CSV, SOL_LABEL_MAP)

    plt.rcParams.update(
        {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 14,
            "axes.titlesize": 16,
            "font.family": "sans-serif",
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5))
    plot_pie(axes[0], base_df)
    plot_pie(axes[1], sol_df)

    axes[0].text(
        0.5,
        -0.5,
        "(a) Revert Reasons in Base.",
        transform=axes[0].transAxes,
        ha="center",
        va="top",
        fontsize=18,
        fontfamily=CAPTION_FONT,
    )
    axes[1].text(
        0.5,
        -0.5,
        "(b) Revert Reasons in Solana.",
        transform=axes[1].transAxes,
        ha="center",
        va="top",
        fontsize=18,
        fontfamily=CAPTION_FONT,
    )

    fig.subplots_adjust(bottom=0.32, wspace=0.2)
    fig.tight_layout()
    fig.savefig(OUTPUT_PDF, format="pdf", bbox_inches="tight")
    plt.close(fig)

    print("Base reasons:")
    print(base_df[["reason", "cnt", "pct"]].to_string(index=False))
    print("Solana reasons:")
    print(sol_df[["reason", "cnt", "pct"]].to_string(index=False))
    print(f"Saved: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
