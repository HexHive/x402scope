#!/usr/bin/env python3
"""Generate Table 5: ATA rent events and sponsor costs.

Input:
  ../ata_rentpayer_by_facilitator.csv

Output:
  table5.csv
"""

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

INPUT_CSV = PROJECT_DIR / "ata_rentpayer_by_facilitator.csv"
OUT_CSV = SCRIPT_DIR / "table5.csv"

RENT_PER_ATA_SOL = Decimal("0.00203928")
SOL_PRICE_USD = Decimal("125")

NAME_MAP = {
    "daydreams": "Daydreams",
    "payai": "PayAI",
    "dexter": "Dexter",
    "ultravioletadao": "UltravioletDAO",
    "aurracloud": "AurraCloud",
    "anyspend": "Anyspend",
    "codenut": "Codenut",
    "openx402": "OpenX402",
    "coinbase": "Coinbase",
    "corbits": "Corbits",
}


def q(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def fmt_int(n: int) -> str:
    return f"{int(n):,}"


def fmt_rent_sol(sol: Decimal) -> str:
    if sol < Decimal("1"):
        return f"{q(sol, '0.001'):.3f}"
    return f"{q(sol, '0.01'):.2f}"


def fmt_rent_usd_from_displayed_sol(sol_display: str) -> str:
    usd = Decimal(sol_display) * SOL_PRICE_USD
    if usd < Decimal("1"):
        return f"${q(usd, '0.01'):.2f}"
    return f"${int(q(usd, '1')):,}"


def load_table() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Missing input {INPUT_CSV}. Run `python ATA_rent_events.py` from the project root first."
        )

    df = pd.read_csv(INPUT_CSV)
    required = ["facilitator", "rent_event_cnt"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{INPUT_CSV} is missing required columns: {missing}")

    df["rent_event_cnt"] = pd.to_numeric(df["rent_event_cnt"], errors="coerce").fillna(0).astype(int)
    df = df.sort_values("rent_event_cnt", ascending=False).reset_index(drop=True)

    rows = []
    for _, row in df.iterrows():
        fac_key = str(row["facilitator"])
        ata_creations = int(row["rent_event_cnt"])
        rent_sol = Decimal(ata_creations) * RENT_PER_ATA_SOL
        rent_sol_display = fmt_rent_sol(rent_sol)
        rows.append(
            {
                "Facilitator": NAME_MAP.get(fac_key.lower(), fac_key),
                "ATA Creations": fmt_int(ata_creations),
                "Rent (SOL)": rent_sol_display,
                "Rent (USD)": fmt_rent_usd_from_displayed_sol(rent_sol_display),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    table = load_table()
    table.to_csv(OUT_CSV, index=False)
    print(table.to_string(index=False))
    print(f"Saved: {OUT_CSV}")


if __name__ == "__main__":
    main()
