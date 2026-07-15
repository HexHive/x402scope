#!/usr/bin/env python3
"""Create a Solana USDC associated token account (ATA).

The payer signs and pays the rent. The owner may be a different wallet. ATA
creation is idempotent: if the ATA already exists, no transaction is sent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SECURITY_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SECURITY_DIR))

import config  # noqa: E402
from simplebase import (  # noqa: E402
    sol_create_associated_token_account_idempotent,
    sol_getAccountInfo,
    sol_maketx,
    sol_topub,
)


NETWORKS = {
    "solana-devnet": {
        "rpc": "https://api.devnet.solana.com",
        "usdc": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
    },
    "solana": {
        "rpc": "https://api.mainnet-beta.solana.com",
        "usdc": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    },
}


def _config_key(name: str) -> str:
    value = getattr(config, name, None)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"config.{name} is missing or empty")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Solana USDC associated token account")
    parser.add_argument("--network", choices=NETWORKS, default="solana-devnet")
    parser.add_argument("--rpc", help="override the network RPC URL")
    parser.add_argument(
        "--payer-key",
        default="solpk",
        help="config.py attribute whose key pays rent and fees (default: solpk)",
    )
    owner = parser.add_mutually_exclusive_group()
    owner.add_argument(
        "--owner-key",
        default="solpk_server",
        help="config.py attribute for the ATA owner (default: solpk_server)",
    )
    owner.add_argument("--owner-address", help="owner public address instead of a config key")
    parser.add_argument("--mint", help="override the USDC mint address")
    parser.add_argument("--yes", action="store_true", help="skip the transaction confirmation")
    args = parser.parse_args()

    network = NETWORKS[args.network]
    rpc = args.rpc or network["rpc"]
    mint = args.mint or network["usdc"]
    payer_key = _config_key(args.payer_key)
    payer_address = sol_topub(payer_key)
    owner_address = args.owner_address or sol_topub(_config_key(args.owner_key))

    # This helper derives the canonical ATA from owner + mint.
    from solders.pubkey import Pubkey
    from solders.token.associated import get_associated_token_address

    try:
        mint_pubkey = Pubkey.from_string(mint)
        owner_pubkey = Pubkey.from_string(owner_address)
        payer_pubkey = Pubkey.from_string(payer_address)
    except Exception as exc:
        raise SystemExit(f"invalid Solana address or mint: {exc}") from exc

    ata = get_associated_token_address(owner_pubkey, mint_pubkey)
    print("network:", args.network)
    print("rpc:", rpc)
    print("mint:", mint)
    print("payer:", payer_address)
    print("owner:", owner_address)
    print("USDC ATA:", ata)

    account_info = sol_getAccountInfo(rpc, str(ata))
    if account_info and account_info.get("value") is not None:
        print("ATA already exists; no transaction sent.")
        return 0

    if not args.yes:
        answer = input("Create this ATA and pay the network rent? Type 'yes' to continue: ")
        if answer != "yes":
            print("cancelled")
            return 1

    instruction = sol_create_associated_token_account_idempotent(
        payer_pubkey,
        owner_pubkey,
        mint_pubkey,
    )
    signature = sol_maketx(
        rpc,
        [instruction],
        payer_key,
        gasprice=1000,
        gaslimit=100_000,
    )
    print("transaction:", signature)
    print("ATA creation submitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
