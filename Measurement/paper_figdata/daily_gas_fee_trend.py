import pandas as pd
import matplotlib.pyplot as plt
from runsql import runsql

BASE_DAY_VIEW = "view39_byday"
SOL_DAY_VIEW  = "solview39_byday"


SOL_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

def extract_base_daily_gas():
    rows = runsql(f"""
        SELECT day, sum_gasfee
        FROM {BASE_DAY_VIEW}
        ORDER BY day
    """)
    df = pd.DataFrame(rows, columns=["day", "base_gasfee_eth"])
    return df

def extract_solana_daily_fee_usdc():
    rows = runsql(f"""
        SELECT day, SUM(sum_fee) AS sol_fee
        FROM {SOL_DAY_VIEW}
        WHERE x402_token = %s
        GROUP BY day
        ORDER BY day
    """, SOL_USDC_MINT)
    df = pd.DataFrame(rows, columns=["day", "sol_fee"])
    return df




def main():
    base = extract_base_daily_gas()
    sol  = extract_solana_daily_fee_usdc()

    merged = pd.merge(base, sol, on="day", how="outer").fillna(0).sort_values("day")
    merged.to_csv("daily_gas_fee_trend.csv", index=False)
    print("Saved: daily_gas_fee_trend.csv")

    total_base_eth = float(merged["base_gasfee_eth"].sum())
    total_sol_fee  = float(merged["sol_fee"].sum())

    print(
        f"USDC-only x402 transactions incurred a total of {total_base_eth:.6f} ETH in gas fees on Base "
        f"(sum of view39_byday.sum_gasfee over the measurement window)."
    )
    print(
        f"On Solana, restricting to USDC mint {SOL_USDC_MINT}, total transaction fees sum to {total_sol_fee:.6f} "
        f"(sum of solview39_byday.sum_fee)."
    )


if __name__ == "__main__":
    main()
