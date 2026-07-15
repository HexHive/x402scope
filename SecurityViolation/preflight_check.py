#!/usr/bin/env python3
"""Read-only environment checks for a reviewer-selected x402 target.

This script deliberately does not contact an RPC, facilitator, merchant, or
chain. It only checks local configuration and import availability before a
state-changing test is run.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from target import FACILITATORS


SCRIPT_DIR = Path(__file__).resolve().parent
CAIP2_SOLANA_DEVNET = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"
CAIP2_SOLANA_MAINNET = "solana:5eykt4UsF8P8NJdTREpY1vzqKqZKvdp"
CAIP2_BASE_SEPOLIA = "eip155:84532"
CAIP2_BASE = "eip155:8453"


@dataclass
class Result:
    errors: int = 0
    warnings: int = 0

    def ok(self, message: str) -> None:
        print(f"PASS  {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"WARN  {message}")

    def fail(self, message: str) -> None:
        self.errors += 1
        print(f"FAIL  {message}")


def _configured(value: object) -> bool:
    if not isinstance(value, str):
        return value is not None
    return bool(value.strip()) and value.strip() not in {"...", "CHANGE_ME", "REPLACE_ME"}


def _check_module(result: Result, module_name: str, package_name: str | None = None) -> None:
    if importlib.util.find_spec(module_name) is None:
        result.fail(f"missing Python dependency: {package_name or module_name}")
    else:
        result.ok(f"Python dependency available: {package_name or module_name}")


def _check_config_value(result: Result, config: object, name: str, required: bool = True) -> None:
    value = getattr(config, name, None)
    if _configured(value):
        result.ok(f"config.{name} is set")
    elif required:
        result.fail(f"config.{name} is missing")
    else:
        result.warn(f"config.{name} is not set (not required for this target)")


def _check_target(result: Result, target_name: str):
    target = FACILITATORS.get(target_name)
    if target is None:
        result.fail(f"unknown target: {target_name}")
        print("Available targets: " + ", ".join(sorted(FACILITATORS)))
        return None

    result.ok(f"target exists: {target_name}")
    for label, value in (
        ("facilitator URL", target.facilitator_base),
        ("merchant URL", target.merchant_base),
        ("pay_to_address", target.pay_to_address),
    ):
        if _configured(value):
            result.ok(f"{label} is configured")
        elif label == "pay_to_address" and "base" in target.network.lower():
            result.warn(f"{label} is empty; the v2 EVM script will derive it from config.pk2")
        else:
            result.fail(f"{label} is missing for {target_name}")

    if target.pay_amount <= 0:
        result.warn(f"pay_amount is {target.pay_amount}; settlement may be intentionally zero-value")
    else:
        result.ok(f"pay_amount is {target.pay_amount}")

    if target.valid_before_offset < 180:
        result.warn(
            f"valid_before_offset is {target.valid_before_offset}s; "
            "normal verify/settle tests should use >180s; "
            "for the free-shopping attack, intentionally reduce it to a small value "
            "such as 8s to find the verify-success/settle-failure boundary"
        )
    else:
        result.ok(
            f"valid_before_offset is {target.valid_before_offset}s; "
            "normal verify/settle tests should use >180s; "
            "before the free-shopping attack, temporarily reduce it to a small value such as 8s"
        )

    return target


def _rpc_call(result: Result, rpc_url: str, method: str, params: list):
    try:
        import requests

        response = requests.post(
            rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise RuntimeError(body["error"])
        return body.get("result")
    except Exception as exc:
        result.fail(f"RPC check failed for {rpc_url}: {exc}")
        return None


def _evm_chain_config(network: str) -> dict | None:
    return {
        "base-sepolia": {
            "rpc": "https://sepolia.base.org",
            "usdc": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        },
        "base": {
            "rpc": "https://mainnet.base.org",
            "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        },
    }.get(network)


def _evm_address(private_key: str) -> str:
    from eth_account import Account

    return Account.from_key(private_key).address


def _check_evm_balances(result: Result, target, config: object) -> None:
    chain = _evm_chain_config(target.network.lower())
    if chain is None:
        result.warn(f"no EVM USDC balance preset for network {target.network}")
        return

    print(f"\nOn-chain EVM balance check: {target.network} (USDC, 6 decimals)")
    accounts = (("pk1", "pk1"), ("pk2", "pk2"), ("poor_pk", "poor_pk"))
    for label, config_name in accounts:
        private_key = getattr(config, config_name, None)
        if not _configured(private_key):
            result.fail(f"cannot check {label}: config.{config_name} is missing")
            continue
        try:
            address = _evm_address(private_key)
        except Exception as exc:
            result.fail(f"cannot derive {label} address: {exc}")
            continue

        calldata = "0x70a08231" + address[2:].lower().rjust(64, "0")
        raw_balance = _rpc_call(
            result,
            chain["rpc"],
            "eth_call",
            [{"to": chain["usdc"], "data": calldata}, "latest"],
        )
        if raw_balance is None:
            continue
        try:
            units = int(raw_balance, 16)
        except (TypeError, ValueError) as exc:
            result.fail(f"invalid USDC balance for {label}: {exc}")
            continue
        result.ok(f"{label} {address}: {units / 1_000_000:.6f} USDC")


def _solana_public_key(private_key: str) -> str:
    from solders.keypair import Keypair

    return str(Keypair.from_base58_string(private_key).pubkey())


def _check_solana_balances(result: Result, target, config: object) -> None:
    devnet = "devnet" in (target.chain_name or target.network).lower()
    rpc_url = "https://api.devnet.solana.com" if devnet else "https://api.mainnet-beta.solana.com"
    mint = (
        "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
        if devnet
        else "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    )
    print(f"\nOn-chain Solana balance/ATA check: {'devnet' if devnet else 'mainnet'} (USDC)")

    try:
        from solders.pubkey import Pubkey
        from solders.token.associated import get_associated_token_address
    except Exception as exc:
        result.fail(f"Solana ATA dependencies unavailable: {exc}")
        return

    accounts = (
        ("solpk", "solpk"),
        ("solpk_server", "solpk_server"),
        ("poor_pk_sol", "poor_pk_sol"),
    )
    # Accept the spelling used in some local reviewer configurations.
    if not _configured(getattr(config, "poor_pk_sol", None)) and _configured(
        getattr(config, "poor_pk_pool", None)
    ):
        accounts = accounts[:-1] + (("poor_pk_pool", "poor_pk_pool"),)

    mint_pubkey = Pubkey.from_string(mint)
    for label, config_name in accounts:
        private_key = getattr(config, config_name, None)
        if not _configured(private_key):
            result.fail(f"cannot check {label}: config.{config_name} is missing")
            continue
        try:
            owner = Pubkey.from_string(_solana_public_key(private_key))
            ata = get_associated_token_address(owner, mint_pubkey)
        except Exception as exc:
            result.fail(f"cannot derive {label} ATA: {exc}")
            continue

        native_balance = _rpc_call(result, rpc_url, "getBalance", [str(owner)])
        if native_balance is not None:
            try:
                lamports = int(native_balance["value"])
                result.ok(f"{label} {owner}: SOL balance={lamports / 1_000_000_000:.9f} SOL")
            except (KeyError, TypeError, ValueError) as exc:
                result.fail(f"invalid SOL balance for {label}: {exc}")

        account_info = _rpc_call(
            result,
            rpc_url,
            "getAccountInfo",
            [str(ata), {"encoding": "jsonParsed"}],
        )
        if account_info is None:
            continue
        if account_info.get("value") is None:
            result.warn(f"{label} {owner}: USDC ATA does not exist ({ata})")
            continue

        balance_info = _rpc_call(
            result,
            rpc_url,
            "getTokenAccountBalance",
            [str(ata)],
        )
        if balance_info is None:
            continue
        amount = balance_info.get("value", {}).get("uiAmountString")
        result.ok(f"{label} {owner}: USDC ATA exists ({ata}), balance={amount} USDC")

    if _configured(target.feepayer):
        fee_payer_balance = _rpc_call(result, rpc_url, "getBalance", [target.feepayer])
        if fee_payer_balance is not None:
            try:
                lamports = int(fee_payer_balance["value"])
                result.ok(
                    f"target.feepayer {target.feepayer}: "
                    f"SOL balance={lamports / 1_000_000_000:.9f} SOL"
                )
            except (KeyError, TypeError, ValueError) as exc:
                result.fail(f"invalid SOL balance for target.feepayer: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run read-only local checks before an x402scope security test."
    )
    parser.add_argument("-t", "--target", required=True, help="target name from SecurityViolation/target.py")
    parser.add_argument(
        "--check-balances",
        action="store_true",
        help="read USDC balances and Solana ATA state through the selected network RPC",
    )
    args = parser.parse_args()

    result = Result()
    print(f"Preflight target: {args.target}")
    if args.check_balances:
        print("Local checks plus read-only RPC balance/ATA checks; no transaction is sent.\n")
    else:
        print("Checks are local-only; no RPC, facilitator, merchant, or chain request is made.\n")

    if sys.version_info >= (3, 10):
        result.ok(f"Python version: {sys.version.split()[0]}")
    else:
        result.fail(f"Python 3.10+ required; found {sys.version.split()[0]}")

    target = _check_target(result, args.target)
    if target is None:
        return 1

    _check_module(result, "requests")

    try:
        import config
    except Exception as exc:
        result.fail(f"cannot import SecurityViolation/config.py: {exc}")
        return 1

    is_solana = "solana" in (target.chain_name or "").lower() or "solana" in target.network.lower()
    facilitator_name = (target.name or "").strip().lower()
    is_coinbase = facilitator_name == "coinbase"

    if is_solana:
        _check_module(result, "solders")
        _check_module(result, "solana")
        _check_config_value(result, config, "solpk")
        _check_config_value(result, config, "poor_pk_sol")
        if not _configured(target.feepayer):
            result.fail("target.feepayer is missing for a Solana settlement test")
        else:
            result.ok("target.feepayer is configured")

        expected_network = (
            CAIP2_SOLANA_DEVNET
            if "devnet" in (target.chain_name or "").lower()
            else CAIP2_SOLANA_MAINNET
        )
        result.ok(f"expected Solana CAIP-2 network: {expected_network}")
    else:
        _check_module(result, "eth_account", "eth-account")
        _check_module(result, "eth_abi", "eth-abi")
        _check_config_value(result, config, "pk1")
        _check_config_value(result, config, "pk2")
        _check_config_value(result, config, "poor_pk")
        expected_network = (
            CAIP2_BASE_SEPOLIA
            if target.network.lower() == "base-sepolia"
            else CAIP2_BASE
            if target.network.lower() == "base"
            else None
        )
        if expected_network:
            result.ok(f"expected EVM CAIP-2 network: {expected_network}")

    if is_coinbase:
        _check_config_value(result, config, "CDP_API_KEY_ID")
        _check_config_value(result, config, "CDP_API_KEY_SECRET")
    elif facilitator_name == "thirdweb":
        _check_config_value(result, config, "ThirdWeb_Secret_key")

    if args.check_balances:
        if is_solana:
            _check_solana_balances(result, target, config)
        else:
            _check_evm_balances(result, target, config)

    print(f"\nSummary: {result.errors} error(s), {result.warnings} warning(s)")
    if result.errors:
        print("Preflight failed; fix the local configuration before running the test.")
        return 1
    print("Preflight passed; you can run the selected test script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
