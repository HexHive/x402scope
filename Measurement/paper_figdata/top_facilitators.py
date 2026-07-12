
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runsql import runsql

VIEW = "view39_byfacilitator_server"

OUT_FAC_SUM = "facilitator_summary.csv"
OUT_TOP10_TX = "top10_facilitators_by_tx.csv"
OUT_TOP10_VOL = "top10_facilitators_by_volume.csv"
OUT_SERVER_MULTI = "server_multi_facilitator.csv"

def fetch_facilitator_summary():
    rows = runsql(f"""
        SELECT
            facilitator,
            SUM(cnt) AS tx_cnt,
            SUM(sum_x402_value) AS volume,
            COUNT(DISTINCT hex_x402_to) AS num_servers,
            SUM(cnt_x402_from) AS approx_num_clients
        FROM {VIEW}
        GROUP BY facilitator
    """)
    return pd.DataFrame(rows, columns=[
        "facilitator", "tx_cnt", "volume", "num_servers", "approx_num_clients"
    ])

def fetch_server_multi():
    rows = runsql(f"""
        SELECT
            hex_x402_to AS server,
            COUNT(DISTINCT facilitator) AS facilitator_cnt,
            SUM(cnt) AS tx_cnt,
            SUM(sum_x402_value) AS volume
        FROM {VIEW}
        GROUP BY hex_x402_to
    """)
    return pd.DataFrame(rows, columns=["server", "facilitator_cnt", "tx_cnt", "volume"])

def main():
    fac = fetch_facilitator_summary()

    # 1) summary
    fac.sort_values("volume", ascending=False).to_csv(OUT_FAC_SUM, index=False)
    print(f"Saved: {OUT_FAC_SUM}")

    # 2) Top10 by tx count
    top10_tx = fac.sort_values("tx_cnt", ascending=False).head(25).copy()
    top10_tx.to_csv(OUT_TOP10_TX, index=False)
    print(f"Saved: {OUT_TOP10_TX}")

    # 3) Top10 by volume
    top10_vol = fac.sort_values("volume", ascending=False).head(25).copy()
    top10_vol.to_csv(OUT_TOP10_VOL, index=False)
    print(f"Saved: {OUT_TOP10_VOL}")

    # 4) Server multi-facilitator analysis
    server = fetch_server_multi()
    server.to_csv(OUT_SERVER_MULTI, index=False)
    print(f"Saved: {OUT_SERVER_MULTI}")

    total_servers = len(server)
    multi = server[server["facilitator_cnt"] > 1]
    multi_ratio = (len(multi) / total_servers * 100) if total_servers else 0.0
    avg_fac_per_server = server["facilitator_cnt"].mean() if total_servers else 0.0

    print("\n=== Server / Facilitator Stats ===")
    print(f"Total servers: {total_servers}")
    print(f"Servers used by >1 facilitator: {len(multi)} ({multi_ratio:.2f}%)")
    print(f"Average facilitators per server: {avg_fac_per_server:.3f}")

if __name__ == "__main__":
    main()
