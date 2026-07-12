"""
Centralized test target configuration.

Each entry in FACILITATORS describes one facilitator + merchant combo so the
other scripts can read consistent settings instead of hard-coding URLs and
amounts. Adjust the values below to your environment, or add more entries if
you test multiple facilitators.

Example usage inside a test script:

    from target import current_target
    cfg = current_target()
    url = cfg.needpay_url          # for client test scripts (e.g., evmclient.py / erc1271test.py)
    settle_url = cfg.settle_url    # for basesupport.py
    payto = cfg.pay_to_address
    payamount = cfg.pay_amount
    chain_name = cfg.chain_name
    valid_after, valid_before = cfg.auth_window()
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict

@dataclass
class FacilitatorTarget:
    name: str
    facilitator_base: str  # 
    merchant_base: str  # e.g. http://127.0.0.1:8001 where /needpay lives
    network: str  # base, base-sepolia, solana
    price: str  # shown on merchant side, server
    pay_to_address: str
    pay_amount: int = 1000  # USDC amount in base units (6 decimals)
    chain_name: str = "base"
    threads: int = 1 
    valid_after_offset: int = -100  # seconds from now
    valid_before_offset: int = 7  # seconds from now
    feepayer: str | None = None  # for Solana tests
    settle_path: str = "/settle"
    needpay_path: str = "/needpay"
    description: str = ""

    @property
    def needpay_url(self) -> str:
        return _join_url(self.merchant_base, self.needpay_path)

    @property
    def settle_url(self) -> str:
        return _join_url(self.facilitator_base, self.settle_path)

    def auth_window(self, now: int | None = None) -> tuple[int, int]:
        """Return (validAfter, validBefore) absolute timestamps."""
        now = int(now or time.time())
        return now + self.valid_after_offset, now + self.valid_before_offset


def _join_url(base: str, path: str) -> str:
    path = path if path.startswith("/") else f"/{path}"
    return base.rstrip("/") + path


# Default entries. Add or edit to fit your environment.
FACILITATORS: Dict[str, FacilitatorTarget] = {
    #Solana testnet
    "coinbase-test": FacilitatorTarget(
        name="coinbase",
        facilitator_base="https://api.cdp.coinbase.com/platform/v2/x402",
        merchant_base="http://127.0.0.1:8001",
        network="base-sepolia",
        price="$0.001",
        pay_to_address="", # Server PUBKEY
        pay_amount=0, # 1000
        threads=1,
        valid_after_offset=-60,
        valid_before_offset=300, # 1 2 3 4 5 6 7 8
        description="Requires CDP API headers; configure in config.py.",
    ),
    #Solana mainnet
    "coinbase-main": FacilitatorTarget(
        name="coinbase",
        facilitator_base="https://api.cdp.coinbase.com/platform/v2/x402",
        merchant_base="http://127.0.0.1:8001",
        network="base",
        price="$0.001",
        pay_to_address="", # Server PUBKEY
        pay_amount=0, # 1000
        threads=1,
        valid_after_offset=-60,
        valid_before_offset=300, # 1 2 3 4 5 6 7 8
        description="Requires CDP API headers; configure in config.py.",
    ),
    #solana testnet
    "coinbase-solanadev": FacilitatorTarget(
        name="coinbase",
        facilitator_base="https://api.cdp.coinbase.com/platform/v2/x402",
        merchant_base="http://127.0.0.1:8001",
        network="solana",
        chain_name="solana-devnet",
        price="$0.001",
        pay_to_address="",  # Server PUBKEY
        feepayer="D6ZhtNQ5nT9ZnTHUbqXZsTx5MH2rPFiBBggX4hY1WePM",
        pay_amount=1000,
        threads=1,
        valid_after_offset=-60,
        valid_before_offset=300,
        description="Requires CDP API headers; configure in config.py.",
    ),
    #Solana mainnet
    "coinbase-solanamain": FacilitatorTarget(
        name="coinbase",
        facilitator_base="https://api.cdp.coinbase.com/platform/v2/x402",
        merchant_base="http://127.0.0.1:8001",
        network="solana",
        chain_name="solana",
        price="$0.001",
        pay_to_address="", # Server PUBKEY
        feepayer="D6ZhtNQ5nT9ZnTHUbqXZsTx5MH2rPFiBBggX4hY1WePM",
        pay_amount=0,
        threads=1,
        valid_after_offset=-60,
        valid_before_offset=300,
        description="Requires CDP API headers; configure in config.py.",
    ),
}

# Which target to use when none is specified
DEFAULT_TARGET = "coinbase-test"


def current_target(name: str | None = None) -> FacilitatorTarget:
    """
    Resolve a target by name. Order of precedence:
    1) Explicit name argument
    2) Environment variable TARGET
    3) DEFAULT_TARGET
    """
    target_name = name or os.getenv("TARGET") or DEFAULT_TARGET
    try:
        return FACILITATORS[target_name]
    except KeyError as exc:
        available = ", ".join(FACILITATORS)
        raise ValueError(f"Unknown target '{target_name}'. Available: {available}") from exc


__all__ = [
    "FacilitatorTarget",
    "FACILITATORS",
    "DEFAULT_TARGET",
    "current_target",
]
