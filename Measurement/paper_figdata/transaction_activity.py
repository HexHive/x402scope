import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runsql import runsql

def get_columns(table: str):
    rows = runsql(f"DESCRIBE {table};")
    return [r[0] for r in rows]

def pick_col(cols, candidates, contains=None):
    colset = set(cols)
    for c in candidates or []:
        if c in colset:
            return c
    if contains:
        for sub in contains:
            for c in cols:
                if sub.lower() in c.lower():
                    return c
    return None

def ensure_cols(table, needed):
    cols = get_columns(table)
    picked = {}
    for key, rule in needed.items():
        picked[key] = pick_col(cols, rule.get("exact"), rule.get("contains"))
        if not picked[key]:
            raise RuntimeError(
                f"[{table}] Cannot find column for '{key}'. "
                f"Tried exact={rule.get('exact')} contains={rule.get('contains')}. "
                f"Available cols={cols}"
            )
    return picked

BASE_DAY_VIEW = "view39_byday"

SOL_DAY_VIEW  = "solview39_byday"

BASE_SERVER_VIEW = "view39_byx402to"
BASE_CLIENT_VIEW = "view39_byfrom"
SOL_SERVER_VIEW  = "solview39_byx402_to"
SOL_CLIENT_VIEW  = "solview39_bypayer"

SOL_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
def extract_daily(view_name: str, prefix: str):
    picked = ensure_cols(view_name, {
        "day": {
            "exact": ["day", "date"],
            "contains": ["day", "date"]
        },
        "tx": {
            "exact": ["cnt", "sum_tx_count", "tx_cnt", "tx_count", "count_tx", "n_tx"],
            "contains": ["tx", "count", "cnt"]
        },
        "usdc": {
            "exact": ["sum_x402_value", "sum_x402_amount", "sum_usdc_value", "usdc", "usdc_value", "sum_value", "value"],
            "contains": ["usdc", "x402", "value", "amount", "volume"]
        }
    })

    day_col  = picked["day"]
    tx_col   = picked["tx"]
    usdc_col = picked["usdc"]

    where_clause = ""
    args = None
    if prefix == "sol":
        where_clause = "WHERE x402_token = %s"
        args = (SOL_USDC_MINT,)

    sql = f"""
        SELECT {day_col} AS day,
               {tx_col} AS tx_cnt,
               {usdc_col} AS usdc_volume
        FROM {view_name}
        {where_clause}
        ORDER BY {day_col}
    """

    rows = runsql(sql, args) if args else runsql(sql)

    return pd.DataFrame(rows, columns=["day", f"{prefix}_tx_cnt", f"{prefix}_usdc_volume"])


def count_distinct(view_name: str):
    cols = get_columns(view_name)
    id_col = pick_col(
        cols,
        candidates=["hex_x402_to", "x402_to", "hex_from", "payer", "from", "address"],
        contains=["x402", "payer", "from", "addr", "address"]
    )
    if not id_col:
        raise RuntimeError(f"[{view_name}] Cannot infer identifier column. cols={cols}")
    n = runsql(f"SELECT COUNT(DISTINCT {id_col}) FROM {view_name};")[0][0]
    return int(n), id_col

def main():
    base_df = extract_daily(BASE_DAY_VIEW, "base")
    sol_df  = extract_daily(SOL_DAY_VIEW, "sol")

    trend = pd.merge(base_df, sol_df, on="day", how="outer").fillna(0).sort_values("day")
    trend.to_csv("trend_daily.csv", index=False)
    print("Saved: trend_daily.csv")

    base_servers, base_server_col = count_distinct(BASE_SERVER_VIEW)
    base_clients, base_client_col = count_distinct(BASE_CLIENT_VIEW)
    sol_servers,  sol_server_col  = count_distinct(SOL_SERVER_VIEW)
    sol_clients,  sol_client_col  = count_distinct(SOL_CLIENT_VIEW)

    contrib = pd.DataFrame([
        {"network": "base", "servers": base_servers, "clients": base_clients,
         "server_id_col": base_server_col, "client_id_col": base_client_col},
        {"network": "solana", "servers": sol_servers, "clients": sol_clients,
         "server_id_col": sol_server_col, "client_id_col": sol_client_col},
    ])
    contrib.to_csv("contributors.csv", index=False)
    print("Saved: contributors.csv")

    print(
        f"Considering USDC-only x402 payments, we observe "
        f"{base_servers} unique servers and {base_clients} unique clients on Base, and "
        f"{sol_servers} unique servers and {sol_clients} unique clients on Solana "
        f"over the measurement window."
    )

if __name__ == "__main__":
    main()
