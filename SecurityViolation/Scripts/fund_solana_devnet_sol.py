#!/usr/bin/env python3
"""Airdrop Devnet SOL to a specified Solana public address.

This uses Solana's public Devnet faucet through ``requestAirdrop``. It does
not require or read a private key; the recipient must sign no transaction.
"""

from __future__ import annotations

import argparse
import time

import requests
from solders.pubkey import Pubkey


DEVNET_RPC = "https://api.devnet.solana.com"
LAMPORTS_PER_SOL = 1_000_000_000
MAX_AIRDROP_SOL = 5.0


def rpc_call(rpc_url: str, method: str, params: list):
    response = requests.post(
        rpc_url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=20,
    )
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        suffix = f" Retry-After: {retry_after}." if retry_after else ""
        raise RuntimeError(
            "Devnet RPC/faucet rate limit reached (HTTP 429). "
            "Wait and retry, or use another Devnet RPC with --rpc."
            + suffix
        )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text[:300].strip()
        raise RuntimeError(f"RPC HTTP {response.status_code}: {detail}") from exc
    body = response.json()
    if body.get("error"):
        raise RuntimeError(body["error"])
    return body.get("result")


def get_sol_balance(rpc_url: str, address: str) -> float:
    result = rpc_call(rpc_url, "getBalance", [address, {"commitment": "confirmed"}])
    return int(result["value"]) / LAMPORTS_PER_SOL


def wait_for_confirmation(rpc_url: str, signature: str, timeout: int = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = rpc_call(
            rpc_url,
            "getSignatureStatuses",
            [[signature], {"searchTransactionHistory": False}],
        )
        status = (result.get("value") or [None])[0]
        if status is not None:
            if status.get("err") is not None:
                raise RuntimeError(f"airdrop transaction failed: {status['err']}")
            if status.get("confirmationStatus") in {"confirmed", "finalized"}:
                return
        time.sleep(1)
    raise TimeoutError(f"timed out waiting for airdrop confirmation: {signature}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Airdrop Devnet SOL to a Solana address")
    parser.add_argument("--to", required=True, help="recipient Solana public address")
    parser.add_argument(
        "--amount",
        type=float,
        default=1.0,
        help="SOL amount to request (default: 1; maximum: 5)",
    )
    parser.add_argument("--rpc", default=DEVNET_RPC, help="Devnet RPC URL override")
    args = parser.parse_args()

    try:
        address = str(Pubkey.from_string(args.to))
    except Exception as exc:
        raise SystemExit(f"invalid Solana public address: {exc}") from exc

    if not 0 < args.amount <= MAX_AIRDROP_SOL:
        raise SystemExit(f"--amount must be greater than 0 and at most {MAX_AIRDROP_SOL} SOL")

    lamports = int(args.amount * LAMPORTS_PER_SOL)
    if lamports <= 0:
        raise SystemExit("--amount is too small")

    print("network: solana-devnet")
    print("rpc:", args.rpc)
    print("recipient:", address)
    print("amount:", lamports / LAMPORTS_PER_SOL, "SOL")
    print("balance before:", get_sol_balance(args.rpc, address), "SOL")

    try:
        signature = rpc_call(args.rpc, "requestAirdrop", [address, lamports])
    except Exception as exc:
        raise SystemExit(f"airdrop request failed: {exc}") from exc
    print("airdrop transaction:", signature)
    wait_for_confirmation(args.rpc, signature)
    print("airdrop confirmed")
    print("balance after:", get_sol_balance(args.rpc, address), "SOL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
