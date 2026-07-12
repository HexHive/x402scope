#!/usr/bin/env python3
"""EVM client-flow test for x402 v2 payment headers.

This client generates a v2 payment payload, encodes it as X-Payment, and calls
SecurityViolation/server_app_v2.py's protected local merchant endpoint.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
from base64 import urlsafe_b64encode

import config
from config import pk1, pk2
from simplebase import Endpoint_Provider, b16e, getsess, sign_eip712, topub
from target import current_target


def _resolve_target_name() -> str:
    for flag in ("-t", "--target"):
        if flag in sys.argv:
            idx = sys.argv.index(flag)
            try:
                return sys.argv[idx + 1]
            except IndexError as exc:
                raise SystemExit("Missing target name after -t/--target") from exc
    if len(sys.argv) > 1:
        return sys.argv[1]
    env_target = os.getenv("TARGET")
    if env_target:
        return env_target
    raise SystemExit("Please specify a target via -t/--target, positional arg, or TARGET env")


CHAIN_PRESETS = {
    "base": {
        "chainid": 8453,
        "name": "base",
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "usdc_version": "2",
        "usdc_name": "USD Coin",
        "endpoints": [
            "https://mainnet.base.org",
            "https://base.public.blockpi.network/v1/rpc/public",
            "https://base-rpc.publicnode.com",
        ],
    },
    "base-sepolia": {
        "chainid": 84532,
        "name": "base-sepolia",
        "usdc": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "usdc_version": "2",
        "usdc_name": "USDC",
        "endpoints": [
            "https://base-sepolia.drpc.org",
            "https://sepolia.base.org",
            "https://base-sepolia-rpc.publicnode.com",
        ],
    },
}


target = current_target(_resolve_target_name())
chain_key = target.network
if chain_key not in CHAIN_PRESETS:
    raise ValueError(f"Unsupported network '{chain_key}'. Known: {', '.join(CHAIN_PRESETS)}")
chain_cfg = CHAIN_PRESETS[chain_key]

chainid = chain_cfg["chainid"]
NETWORK = f"eip155:{chainid}"
USDC = chain_cfg["usdc"]
USDC_VERSION = chain_cfg["usdc_version"]
USDC_NAME = chain_cfg["usdc_name"]
p = Endpoint_Provider(chain_cfg["endpoints"])

# Match the legacy evmclient.py behavior for Base Sepolia unless overridden.
testnet_pk = "1" * 64
use_testnet_key = chain_key.endswith("sepolia") and not os.getenv("X402_USE_CONFIG_PK1")
pk = testnet_pk if use_testnet_key else pk1
config.privatekey = pk
MYADDR = topub(pk)
payto = target.pay_to_address or topub(pk2)
payamount = target.pay_amount
url = target.needpay_url


def create_v2_payment_payload() -> dict:
    ts = int(time.time())
    valid_after, valid_before = target.auth_window(ts)
    nonce_bytes = secrets.token_bytes(32)
    typed_data = {
        "types": {
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ]
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": USDC_NAME,
            "version": USDC_VERSION,
            "chainId": chainid,
            "verifyingContract": USDC,
        },
        "message": {
            "from": MYADDR,
            "to": payto,
            "value": payamount,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce_bytes,
        },
    }
    sig = sign_eip712(typed_data, pk)
    requirements = {
        "scheme": "exact",
        "network": NETWORK,
        "asset": USDC,
        "amount": str(payamount),
        "payTo": payto,
        "maxTimeoutSeconds": 60,
        "extra": {
            "name": USDC_NAME,
            "version": USDC_VERSION,
        },
    }
    return {
        "x402Version": 2,
        "resource": {
            "url": url,
            "description": "",
            "mimeType": "",
        },
        "accepted": requirements,
        "payload": {
            "signature": sig,
            "authorization": {
                "from": MYADDR,
                "to": payto,
                "value": str(payamount),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": b16e(nonce_bytes),
            },
        },
    }


def create_header() -> str:
    payload = create_v2_payment_payload()
    payment_header = urlsafe_b64encode(json.dumps(payload).encode("ascii")).decode()
    print("paymentheader:")
    print(payment_header)
    return payment_header


def run(target_name=None):
    if target_name:
        os.environ["TARGET"] = target_name

    bal = p.erc20_balanceOf(USDC, MYADDR)
    print(f"MYADDR: {MYADDR}")
    print(f"MY Balance: {bal / 1e6}")
    assert bal > payamount, "payer USDC balance must be greater than target.pay_amount"

    payment_header = create_header()
    x = getsess().get(url, headers={"X-Payment": payment_header})
    print(x, x.headers)
    print(x.text)


def main():
    run()


if __name__ == "__main__":
    main()
