#!/usr/bin/env python3
"""Generate Table 4: Revert statistics summary.

Input:
  ../failrate_summary.csv

Output:
  table4.csv
"""

from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

INPUT_CSV = PROJECT_DIR / "failrate_summary.csv"
OUT_CSV = SCRIPT_DIR / "table4.csv"


def fmt_int(x) -> str:
    return f"{int(x):,}"


def fmt_rate(network: str, rate: float) -> str:
    if str(network).lower() == "solana":
        return f"{rate * 100:.3f}%"
    return f"{rate * 100:.2f}%"


def load_table() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Missing input {INPUT_CSV}. Run `python revert_statistics.py` from the project root first."
        )

    df = pd.read_csv(INPUT_CSV)
    required = ["network", "success_cnt", "fail_cnt", "fail_rate"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{INPUT_CSV} is missing required columns: {missing}")

    order = {"Base": 0, "Solana": 1}
    df["_order"] = df["network"].map(order).fillna(99)
    df = df.sort_values("_order").drop(columns=["_order"])

    return pd.DataFrame(
        {
            "Network": df["network"],
            "Success": df["success_cnt"].map(fmt_int),
            "Reverted": df["fail_cnt"].map(fmt_int),
            "Revert Rate": [fmt_rate(n, r) for n, r in zip(df["network"], df["fail_rate"])],
        }
    )


def main() -> None:
    table = load_table()
    table.to_csv(OUT_CSV, index=False)
    print(table.to_string(index=False))
    print(f"Saved: {OUT_CSV}")


if __name__ == "__main__":
    main()
