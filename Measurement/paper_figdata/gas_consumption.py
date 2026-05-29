import pandas as pd
from runsql import runsql

SOL_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
OUT_CSV = "gas_total.csv"

def q_scalar(sql: str) -> float:
    rows = runsql(sql)
    v = rows[0][0] if rows and rows[0] else 0
    return float(v or 0)

def q_count_and_sum(sql: str):
    rows = runsql(sql)
    cnt = int((rows[0][0] if rows and rows[0] else 0) or 0)
    s = float((rows[0][1] if rows and rows[0] else 0) or 0)
    return cnt, s

# ---------------- Base totals ----------------
def get_base_success_gas_eth() -> float:
    return q_scalar("SELECT SUM(sum_gasfee) FROM view39_byday")

def get_base_revert_gas_eth():
    return q_count_and_sum("SELECT COUNT(*), SUM(gasfee) FROM view39_raw_reverted")

# ---------------- Solana totals ----------------
SOL_X402_CATS_SQL = "('x402_token','x402_token_ata','x402_token2022','x402_token2022_ata')"
SOL_ATA_CATS_SQL  = "('x402_token_ata','x402_token2022_ata')"

def get_solana_success_fee_total():
    sql = f"""
        SELECT COUNT(*), SUM(fee)
        FROM solanatxs
        WHERE ok = 1
          AND x402_token = '{SOL_USDC_MINT}'
          AND tx_category IN {SOL_X402_CATS_SQL}
    """
    return q_count_and_sum(sql)

def get_solana_failed_fee_total():
    sql = f"""
        SELECT COUNT(*), SUM(fee)
        FROM solanatxs
        WHERE ok = 0
          AND x402_token = '{SOL_USDC_MINT}'
          AND tx_category IN {SOL_X402_CATS_SQL}
    """
    return q_count_and_sum(sql)

def get_solana_ata_cnt():
    sql = f"""
        SELECT COUNT(*)
        FROM solanatxs
        WHERE ok = 1
          AND x402_token = '{SOL_USDC_MINT}'
          AND tx_category IN {SOL_ATA_CATS_SQL}
    """
    return int(q_scalar(sql) or 0)

# ---------------- Main ----------------
def main():
    # Base
    base_success_eth = get_base_success_gas_eth()
    base_revert_cnt, base_revert_eth = get_base_revert_gas_eth()

    # Solana
    sol_success_cnt, sol_success_fee = get_solana_success_fee_total()
    sol_failed_cnt, sol_failed_fee = get_solana_failed_fee_total()

    out = pd.DataFrame([{
        "base_success_gas_eth": base_success_eth,
        "base_revert_gas_eth": base_revert_eth,
        "base_revert_cnt": base_revert_cnt,

        "sol_success_fee_sol": sol_success_fee,
        "sol_success_cnt": sol_success_cnt,

        "sol_failed_fee_sol": sol_failed_fee,
        "sol_failed_cnt": sol_failed_cnt,

        "sol_usdc_mint": SOL_USDC_MINT,
    }])

    out.to_csv(OUT_CSV, index=False)
    print(f"Saved: {OUT_CSV}\n")

    print("====== Totals ======")
    print(f"Base success gas: {base_success_eth:.6f} ETH")
    print(f"Base revert gas:  {base_revert_eth:.6f} ETH  (reverted txs: {base_revert_cnt})")

    print()
    print(f"Sol success fee:  {sol_success_fee:.6f} SOL (success txs: {sol_success_cnt})")
    print(f"Sol failed fee:   {sol_failed_fee:.6f} SOL (failed txs: {sol_failed_cnt})")

    base_total = base_success_eth + base_revert_eth
    if base_total > 0:
        print(f"\nBase revert share: {base_revert_eth / base_total * 100:.2f}%")

    sol_total = sol_success_fee + sol_failed_fee
    if sol_total > 0:
        print(f"Sol failed fee share: {sol_failed_fee / sol_total * 100:.2f}%")

if __name__ == "__main__":
    main()
