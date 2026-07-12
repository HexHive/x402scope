#!/usr/bin/env python3
"""Transfer USDC from a local config.py EVM account.

Default use case for the artifact tests:
    python3 SecurityViolation/Scripts/transfer_usdc.py \
        --network base-sepolia \
        --to 0x844482ab5C69997a79af12148344A3038Dd667D1 \
        --amount 0.01

By default this script uses the shared Base Sepolia test account used by the
EVM test scripts: private key 0x111...111, address
0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A. It does not use pk1/pk2 unless
explicitly requested with --key-name pk1 or --key-name pk2.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from web3 import Web3

SCRIPT_DIR = Path(__file__).resolve().parent
SECURITY_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SECURITY_DIR))

import config  # noqa: E402
from simplebase import topub  # noqa: E402

NETWORKS = {
    "base-sepolia": {
        "chain_id": 84532,
        "rpc": "https://sepolia.base.org",
        "usdc": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    },
    "base": {
        "chain_id": 8453,
        "rpc": "https://mainnet.base.org",
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    },
}

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "recipient", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]


def _resolve_private_key(key_name: str) -> str:
    if key_name in {"testnet_pk", "sepolia_testnet_pk"}:
        return "1" * 64
    if not hasattr(config, key_name):
        raise SystemExit(f"config.py has no key named {key_name!r}")
    private_key = getattr(config, key_name)
    if not private_key:
        raise SystemExit(f"config.{key_name} is empty")
    return private_key


def _amount_to_units(amount: str) -> int:
    value = Decimal(amount)
    if value <= 0:
        raise ValueError("amount must be positive")
    return int(value * Decimal(10**6))


def _fmt_units(value: int) -> str:
    return str(Decimal(value) / Decimal(10**6))


def _add_fees(w3: Web3, tx: dict) -> dict:
    latest = w3.eth.get_block("latest")
    if "baseFeePerGas" in latest:
        priority = w3.to_wei(0.01, "gwei")
        tx["maxPriorityFeePerGas"] = priority
        tx["maxFeePerGas"] = int(latest["baseFeePerGas"] * 2 + priority)
    else:
        tx["gasPrice"] = w3.eth.gas_price
    return tx


def main() -> int:
    parser = argparse.ArgumentParser(description="Transfer USDC from a local config.py key")
    parser.add_argument("--network", choices=NETWORKS, default="base-sepolia")
    parser.add_argument("--rpc", help="override RPC URL")
    parser.add_argument("--to", default="0x844482ab5C69997a79af12148344A3038Dd667D1")
    parser.add_argument("--amount", default="0.01", help="USDC amount in human units, default 0.01")
    parser.add_argument(
        "--key-name",
        default="testnet_pk",
        help="key to use: testnet_pk for 0x19E7... or a SecurityViolation/config.py key name such as pk1/pk2; default testnet_pk",
    )
    parser.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    args = parser.parse_args()

    private_key = _resolve_private_key(args.key_name)

    sender_from_key = topub(private_key)
    acct = Web3().eth.account.from_key(private_key)
    if acct.address.lower() != sender_from_key.lower():
        raise SystemExit("internal address mismatch while loading private key")

    net = NETWORKS[args.network]
    rpc = args.rpc or net["rpc"]
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        raise SystemExit(f"Could not connect to RPC: {rpc}")
    chain_id = w3.eth.chain_id
    if chain_id != net["chain_id"]:
        raise SystemExit(f"RPC chain id mismatch: got {chain_id}, expected {net['chain_id']}")

    to = Web3.to_checksum_address(args.to)
    token = w3.eth.contract(address=Web3.to_checksum_address(net["usdc"]), abi=ERC20_ABI)
    amount_units = _amount_to_units(args.amount)

    sender_bal = token.functions.balanceOf(acct.address).call()
    receiver_bal = token.functions.balanceOf(to).call()
    eth_bal = w3.eth.get_balance(acct.address)

    print("network:", args.network)
    print("rpc:", rpc)
    print("token:", net["usdc"])
    print("from key:", args.key_name)
    print("from:", acct.address)
    print("to:", to)
    print("amount USDC:", _fmt_units(amount_units))
    print("from USDC before:", _fmt_units(sender_bal))
    print("to USDC before:", _fmt_units(receiver_bal))
    print("from ETH before:", w3.from_wei(eth_bal, "ether"))

    if sender_bal < amount_units:
        raise SystemExit("insufficient USDC balance")
    if eth_bal == 0:
        raise SystemExit("sender has no ETH for gas")

    if not args.yes:
        ans = input("Send transaction? Type 'yes' to continue: ")
        if ans != "yes":
            print("cancelled")
            return 1

    tx = token.functions.transfer(to, amount_units).build_transaction(
        {
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "chainId": chain_id,
        }
    )
    tx = _add_fees(w3, tx)
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)

    signed = acct.sign_transaction(tx)
    raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    print("tx:", tx_hash.hex())
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("receipt status:", receipt.status)
    if receipt.status != 1:
        raise SystemExit("transfer reverted")

    print("from USDC after:", _fmt_units(token.functions.balanceOf(acct.address).call()))
    print("to USDC after:", _fmt_units(token.functions.balanceOf(to).call()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
