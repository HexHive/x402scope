#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _print_rows(rows: list[dict]) -> None:
    if not rows:
        print("No transactions found.")
        return
    for row in rows:
        print(
            f"hash={row['hash']}  block/slot={row['block']}  time={row['time']}  "
            f"from={row['from']}  to={row['to']}  value={row['value']}  status={row['status']}"
        )


def fetch_evm(address: str, rpc: str, limit: int, max_blocks: int) -> list[dict]:
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc))
    if not w3.is_connected():
        raise SystemExit("Failed to connect to EVM RPC")

    addr = w3.to_checksum_address(address)
    latest_block = w3.eth.block_number
    rows: list[dict] = []

    for bn in range(latest_block, max(latest_block - max_blocks, -1), -1):
        block = w3.eth.get_block(bn, full_transactions=True)
        block_ts = block.get("timestamp")
        for tx in block["transactions"]:
            if tx["from"] == addr or (tx["to"] and tx["to"] == addr):
                receipt = w3.eth.get_transaction_receipt(tx["hash"])
                status = "success" if receipt.status == 1 else "failed"
                rows.append(
                    {
                        "hash": tx["hash"].hex(),
                        "block": tx["blockNumber"],
                        "time": _fmt_ts(block_ts),
                        "from": tx["from"],
                        "to": tx["to"] or "contract-creation",
                        "value": w3.from_wei(tx["value"], "ether"),
                        "status": status,
                    }
                )
                if len(rows) >= limit:
                    return rows
        if len(rows) >= limit:
            break
    return rows


def fetch_solana(address: str, rpc: str, limit: int) -> list[dict]:
    from solana.rpc.api import Client

    client = Client(rpc)
    resp = client.get_signatures_for_address(address, limit=limit)
    if resp.get("error"):
        raise SystemExit(f"Solana RPC error: {resp['error']}")

    rows: list[dict] = []
    for item in resp["result"]:
        sig = item["signature"]
        tx_resp = client.get_transaction(sig, encoding="jsonParsed")
        tx = tx_resp.get("result")
        if not tx:
            continue
        meta = tx.get("meta", {})
        block_time = tx.get("blockTime")
        err = meta.get("err")
        status = "success" if err is None else "failed"
        rows.append(
            {
                "hash": sig,
                "block": tx.get("slot"),
                "time": _fmt_ts(block_time),
                "from": tx.get("transaction", {}).get("message", {}).get("accountKeys", [{}])[0].get("pubkey", "-"),
                "to": "-",
                "value": f"fee={meta.get('fee', '-')}",
                "status": status,
            }
        )
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="Track latest transactions for an address (EVM or Solana).")
    p.add_argument("--chain", choices=["evm", "solana"], required=True)
    p.add_argument("--address", required=True)
    p.add_argument("--rpc", required=True, help="RPC URL for the selected chain")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--max-blocks", type=int, default=2000, help="EVM only: scan back N blocks")
    args = p.parse_args()

    if args.chain == "evm":
        rows = fetch_evm(args.address, args.rpc, args.limit, args.max_blocks)
    else:
        rows = fetch_solana(args.address, args.rpc, args.limit)
    _print_rows(rows)


if __name__ == "__main__":
    main()
