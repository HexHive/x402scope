############################### Verify-Base (v2)
import os
import sys
import secrets
import csv
import datetime as dt
import copy
import time
import random
from pathlib import Path

from simplebase import * 
import config
from target import current_target
from config import pk1, pk2
from oracles import log_verify_result, _print_api_result, tee_run_log


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

target = current_target(_resolve_target_name())
chain_key = target.network
if chain_key not in CHAIN_PRESETS:
    raise ValueError(f"Unsupported chain_name '{chain_key}'. Known: {', '.join(CHAIN_PRESETS)}")
chain_cfg = CHAIN_PRESETS[chain_key]

chainid = chain_cfg["chainid"]
CHAINNAME = f"eip155:{chainid}"  # x402 v2 uses CAIP-2 network identifiers

USDC = chain_cfg["usdc"]
USDC_version = chain_cfg["usdc_version"]
USDC_name = chain_cfg["usdc_name"]


testnet_pk = "1" * 64  
use_testnet_key = chain_key.endswith("sepolia")
pk = testnet_pk if use_testnet_key else pk1
config.privatekey = pk  # keep simplebase helpers aligned
MYADDR = topub(pk)
payto = target.pay_to_address or topub(pk2)
payamount = target.pay_amount  # to test if min amount of money that facilitator requests


def create_payload_v2(
    valid_after=None,
    valid_before=None,
    nonce_bytes=None,
    payer_addr=None,
    payer_pk=None,
    pay_to=None,
    amount=None,
):
    ts = int(time.time())
    if valid_after is None or valid_before is None:
        valid_after, valid_before = target.auth_window(ts)
    if nonce_bytes is None:
        nonce_bytes = secrets.token_bytes(32)
    if payer_addr is None:
        payer_addr = MYADDR
    if payer_pk is None:
        payer_pk = pk
    if pay_to is None:
        pay_to = payto
    if amount is None:
        amount = payamount

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
            "name": USDC_name,
            "version": USDC_version,
            "chainId": chainid,
            "verifyingContract": USDC,
        },
        "message": {
            "from": payer_addr,
            "to": pay_to,
            "value": amount,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce_bytes,
        },
    }
    sig = sign_eip712(typed_data, payer_pk)

    requirements = {
        "scheme": "exact",
        "network": CHAINNAME,
        "asset": USDC,
        "amount": str(amount),
        "payTo": pay_to,
        "maxTimeoutSeconds": 60,
        "extra": {
            "name": USDC_name,
            "version": USDC_version,
        },
    }

    payload = {
        "x402Version": 2,
        "resource": {
            "url": target.needpay_url,
            "description": "",
            "mimeType": "",
        },
        "accepted": requirements,
        "payload": {
            "signature": sig,
            "authorization": {
                "from": payer_addr,
                "to": pay_to,
                "value": str(amount),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": b16e(nonce_bytes),
            },
        },
    }

    return payload, requirements


payment_payload, payment_requirements = create_payload_v2()
data = {
    "x402Version": 2,
    "paymentPayload": payment_payload,
    "paymentRequirements": payment_requirements,
}

url = target.facilitator_base.rstrip("/") + "/verify"
headers = {}
settle_url = target.settle_url
settle_headers = {}

# Coinbase facilitator needs CDP API headers
if "coinbase" in target.name:
    from config import CDP_API_KEY_ID, CDP_API_KEY_SECRET
    from cdp.x402 import create_facilitator_config
    import asyncio

    facilitator_config = create_facilitator_config(
        api_key_id=CDP_API_KEY_ID,
        api_key_secret=CDP_API_KEY_SECRET,
    )
    headers.update(asyncio.run(facilitator_config["create_headers"]())["verify"])
    url = facilitator_config["url"] + "/verify"
    settle_headers.update(asyncio.run(facilitator_config["create_headers"]())["settle"])
    settle_url = facilitator_config["url"] + "/settle"
elif "thirdweb" in target.name:
    try:
        from config import ThirdWeb_Secret_key
    except Exception as exc:
        raise SystemExit("thirdweb target requires ThirdWeb_Secret_key in config.py") from exc
    headers["x-secret-key"] = ThirdWeb_Secret_key
    settle_headers["x-secret-key"] = ThirdWeb_Secret_key

if "codenut" in target.name:
    SCRIPT_DIR = Path(__file__).resolve().parent
    CA_PATH = SCRIPT_DIR / "codenut.crt"
    # sess.verify = str(CA_PATH)
    sess.verify = False






def run(target_name=None):
    import os
    if target_name:
        os.environ["TARGET"] = target_name

    # ### correctness_test
    print("############ Correctness Test")
    print(url)
    x = sess.post(url, json=data, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data, x, payment_payload)

    print(settle_url)
    x = sess.post(settle_url, json=data, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data, x, payment_payload)


    ### scheme_test
    print("############ scheme_test")
    print("############ Oracle: verify succeed -> SR1")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    print(url)
    ######################################################
    # sanitized mutations
    #######################################################
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))

    ## network_test
    print("############ network_test")
    print("############ Oracle: verify succeed -> SR1")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))

    ### signature_test1
    print("############ signature_test")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))


    ### pay_to_test and SR2
    print("############ pay_to_test")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut)
    time.sleep(2 + random.uniform(0, 0.5))

    ### pay_amount_test
    print("############ pay_amount_test")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))


    ### insufficient_balance_test
    print("############ insufficient_balance_testing")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut)
    time.sleep(2 + random.uniform(0, 0.5))


    ### expired_validbefore_test
    print("############ expired_validbefore_test")
    print("############ Oracle: verify succeed -> SR3")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")、
    ts = int(time.time())
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut)
    time.sleep(2 + random.uniform(0, 0.5))


    ### tofar_validafter_test
    print("############ toofar_validafter_test")
    print("############ Oracle: verify succeed -> SR3")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ts = int(time.time())
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut)
    time.sleep(2 + random.uniform(0, 0.5))


    ### replay_nonce
    print("############ replay_nonce, check if settle, check if new block")
    print("############ Oracle: verify succeed -> SR3")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload)
    time.sleep(2 + random.uniform(0, 0.5))

def main():
    with tee_run_log(Path(__file__).stem, target.name):
        run()


if __name__ == "__main__":
    main()
