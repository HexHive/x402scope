#!/usr/bin/env python3
"""Generate Table 6: ATA creation distribution by owner.

Input:
  ../ata_owner_counts.csv

Output:
  table6.csv
"""

from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

INPUT_CSV = PROJECT_DIR / "ata_owner_counts.csv"
OUT_CSV = SCRIPT_DIR / "table6.csv"

BUCKETS = ["1", "2–10", "11–100", "101–1000", "> 1000"]


def fmt_int(n: int) -> str:
    return f"{int(n):,}"


def load_counts() -> pd.Series:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Missing input {INPUT_CSV}. Run `python ATA_owner_distribution.py` from the project root first."
        )

    df = pd.read_csv(INPUT_CSV)
    required = ["ata_owner", "tx_cnt"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{INPUT_CSV} is missing required columns: {missing}")

    counts = pd.to_numeric(df["tx_cnt"], errors="coerce").fillna(0).astype(int)
    counts = counts[counts >= 0]
    return counts


def build_table() -> pd.DataFrame:
    counts = load_counts()
    bucket_counts = {
        "1": int((counts == 1).sum()),
        "2–10": int(((counts >= 2) & (counts <= 10)).sum()),
        "11–100": int(((counts >= 11) & (counts <= 100)).sum()),
        "101–1000": int(((counts >= 101) & (counts <= 1000)).sum()),
        "> 1000": int((counts > 1000).sum()),
    }

    return pd.DataFrame(
        [
            {"Metric": "ATAs/Owner", **{bucket: bucket for bucket in BUCKETS}},
            {"Metric": "Owners", **{bucket: fmt_int(bucket_counts[bucket]) for bucket in BUCKETS}},
        ]
    )


def main() -> None:
    table = build_table()
    table.to_csv(OUT_CSV, index=False)
    print(table.to_string(index=False))
    print(f"Saved: {OUT_CSV}")


if __name__ == "__main__":
    main()
