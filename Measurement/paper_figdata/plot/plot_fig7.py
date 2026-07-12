#!/usr/bin/env python3
"""Generate Figure 7: ATA owner concentration.

Input:
  ../ata_owner_counts.csv

Output:
  fig7.pdf
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

INPUT_CSV = PROJECT_DIR / "ata_owner_counts.csv"
OUTPUT_PDF = SCRIPT_DIR / "fig7.pdf"

OWNER_COL = "ata_owner"
COUNT_COL = "tx_cnt"


def lorenz_curve(counts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return Lorenz curve coordinates for non-negative counts."""
    counts = np.asarray(counts, dtype=np.float64)
    counts = counts[np.isfinite(counts)]
    counts = counts[counts >= 0]

    if counts.size == 0:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0])

    sorted_counts = np.sort(counts)
    cum = np.cumsum(sorted_counts)
    total = cum[-1]

    if total <= 0:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0])

    y = np.insert(cum / total, 0, 0.0)
    x = np.linspace(0.0, 1.0, len(y))
    return x, y


def gini_from_counts(counts: np.ndarray) -> float:
    """Compute Gini coefficient from non-negative counts."""
    counts = np.asarray(counts, dtype=np.float64)
    counts = counts[np.isfinite(counts)]
    counts = counts[counts >= 0]

    if counts.size == 0 or np.all(counts == 0):
        return 0.0

    sorted_counts = np.sort(counts)
    n = sorted_counts.size
    total = sorted_counts.sum()
    ranks = np.arange(1, n + 1, dtype=np.float64)
    return float((2.0 * np.sum(ranks * sorted_counts)) / (n * total) - (n + 1.0) / n)


def load_counts() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Missing input {INPUT_CSV}. Run `python ATA_owner_distribution.py` from the project root first."
        )

    df = pd.read_csv(INPUT_CSV)
    missing = [c for c in [OWNER_COL, COUNT_COL] if c not in df.columns]
    if missing:
        raise ValueError(f"{INPUT_CSV} is missing required columns: {missing}")

    df[COUNT_COL] = pd.to_numeric(df[COUNT_COL], errors="coerce").fillna(0)
    df = df[df[COUNT_COL] >= 0].copy()
    if df.empty:
        raise ValueError(f"No non-negative owner-count rows found in {INPUT_CSV}")
    return df


def plot_fig7() -> None:
    df = load_counts()
    counts = df[COUNT_COL].to_numpy(dtype=np.float64)
    n_owners = len(counts)
    total_ata = int(counts.sum())
    gini = gini_from_counts(counts)
    x_lor, y_lor = lorenz_curve(counts)

    plt.rcParams.update(
        {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 15,
            "axes.labelsize": 18,
            "axes.titlesize": 12,
            "xtick.labelsize": 18,
            "ytick.labelsize": 18,
            "legend.fontsize": 18,
        }
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.subplots_adjust(left=0.18)

    ax.plot(x_lor, y_lor, linewidth=3, label="Lorenz curve")
    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=3, label="Equality")

    ax.set_xlabel("Cumulative fraction of owners")
    ax.set_ylabel("Cumulative fraction of ATAs")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False)

    ax.text(
        0.65,
        0.65,
        f"Gini = {gini:.3f}\n(n={n_owners:,})",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=18,
    )

    fig.tight_layout()
    fig.savefig(OUTPUT_PDF, format="pdf", bbox_inches="tight")
    plt.close(fig)

    print(f"Owners: {n_owners:,}")
    print(f"ATA events: {total_ata:,}")
    print(f"Gini: {gini:.6f}")
    print(f"Saved: {OUTPUT_PDF}")


def main() -> None:
    plot_fig7()


if __name__ == "__main__":
    main()
