
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runsql import runsql


BASE_VIEW = "view39_byfrom"        
SOL_VIEW  = "solview39_bypayer" 


SOL_FAILED_TABLE = "solanatxs_failed"


SOL_X402_CATS_SQL = "('x402_token','x402_token_ata','x402_token2022','x402_token2022_ata')"


SOL_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"



def save_df(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)
    print(f"Saved: {path}")




def fetch_failrate_summary():
    base_row = runsql(f"""
        SELECT
          SUM(CASE WHEN status=1 THEN cnt ELSE 0 END) AS success_cnt,
          SUM(CASE WHEN status=0 THEN cnt ELSE 0 END) AS fail_cnt,
          SUM(cnt) AS total_cnt
        FROM {BASE_VIEW}
        WHERE tx_category='x';
    """)[0]

    base_success = int(base_row[0] or 0)
    base_fail    = int(base_row[1] or 0)
    base_total   = int(base_row[2] or 0)
    base_fail_rate = (base_fail / base_total) if base_total else 0.0

    sol_row = runsql(f"""
        SELECT
          SUM(CASE WHEN ok=1 THEN cnt ELSE 0 END) AS success_cnt,
          SUM(CASE WHEN ok=0 THEN cnt ELSE 0 END) AS fail_cnt,
          SUM(cnt) AS total_cnt
        FROM {SOL_VIEW}
        WHERE tx_category IN {SOL_X402_CATS_SQL};
    """)[0]

    sol_success = int(sol_row[0] or 0)
    sol_fail    = int(sol_row[1] or 0)
    sol_total   = int(sol_row[2] or 0)
    sol_fail_rate = (sol_fail / sol_total) if sol_total else 0.0

    df = pd.DataFrame([
        {"network": "Base",   "success_cnt": base_success, "fail_cnt": base_fail, "total_cnt": base_total, "fail_rate": base_fail_rate},
        {"network": "Solana", "success_cnt": sol_success,  "fail_cnt": sol_fail,  "total_cnt": sol_total,  "fail_rate": sol_fail_rate},
    ])
    return df


def fetch_base_revert_breakdown():
    rows = runsql(f"""
        SELECT
          COALESCE(NULLIF(revertreason,''), 'Unknown') AS reason,
          SUM(cnt) AS cnt
        FROM {BASE_VIEW}
        WHERE tx_category='x' AND status=0
        GROUP BY reason
        ORDER BY cnt DESC;
    """)
    return pd.DataFrame(rows, columns=["reason", "cnt"])


def fetch_solana_fail_breakdown():
    rows = runsql(f"""
        SELECT
          COALESCE(NULLIF(revertreason,''), 'Unknown') AS reason,
          COUNT(*) AS cnt
        FROM {SOL_FAILED_TABLE}
        WHERE tx_category IN {SOL_X402_CATS_SQL}
          AND x402_token = %s
        GROUP BY reason
        ORDER BY cnt DESC;
    """, (SOL_USDC_MINT,))
    return pd.DataFrame(rows, columns=["reason", "cnt"])



def main():
    summary = fetch_failrate_summary()
    save_df(summary, "failrate_summary.csv")

    base = summary[summary["network"] == "Base"].iloc[0].to_dict()
    sol  = summary[summary["network"] == "Solana"].iloc[0].to_dict()

    print(
        f"x402 transactions fail at a rate of {base['fail_rate']*100:.2f}% on Base "
        f"({int(base['fail_cnt'])}/{int(base['total_cnt'])}), and {sol['fail_rate']*100:.2f}% on Solana "
        f"({int(sol['fail_cnt'])}/{int(sol['total_cnt'])})."
    )

    base_rev = fetch_base_revert_breakdown()
    save_df(base_rev, "base_revert_breakdown.csv")


    sol_fail = fetch_solana_fail_breakdown()
    save_df(sol_fail, "solana_fail_breakdown.csv")



if __name__ == "__main__":
    main()
