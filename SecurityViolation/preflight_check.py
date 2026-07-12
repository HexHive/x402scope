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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run read-only local checks before an x402scope security test."
    )
    parser.add_argument("-t", "--target", required=True, help="target name from SecurityViolation/target.py")
    args = parser.parse_args()

    result = Result()
    print(f"Preflight target: {args.target}")
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

    print(f"\nSummary: {result.errors} error(s), {result.warnings} warning(s)")
    if result.errors:
        print("Preflight failed; fix the local configuration before running the test.")
        return 1
    print("Preflight passed; you can run the selected test script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
