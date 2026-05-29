############################### Verify-Base
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
from config import pk1,pk2,poor_pk
from oracles import log_verify_result, _print_api_result

LOG_SEQ = 0
PRINT_SEQ = 0


def _log_seq() -> int:
    global LOG_SEQ
    LOG_SEQ += 1
    return LOG_SEQ


def _print_seq() -> int:
    global PRINT_SEQ
    PRINT_SEQ += 1
    return PRINT_SEQ


def _print_step(title: str):
    print(f"### {_print_seq()}. {title}")


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
CHAINNAME = target.network  # network in header must match server requirements
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

import secrets

def create_header(returnpayload=False):
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
            "name": USDC_name,
            "version": USDC_version,
            "chainId": chainid,
            "verifyingContract": USDC,
        },
        "message": {
            "from": MYADDR,
            "to": payto,
            "value": payamount,
            "validAfter": valid_after,  
            "validBefore": valid_before,   # to test time window
            "nonce": nonce_bytes,
        },
    }
    sig = sign_eip712(typed_data, pk)
    payload = {
        "x402Version":1,
        "scheme":"exact",
        "network": CHAINNAME,
        "payload":{
            "signature":sig,
            "authorization":{
                "from":MYADDR,
                "to":payto,
                "value":str(payamount),
                "validAfter":str(typed_data["message"]["validAfter"]),
                "validBefore":str(typed_data["message"]["validBefore"]),
                "nonce":b16e(nonce_bytes)
            }
        }
    }
    if returnpayload:
        return payload
    paymentheader = urlsafe_b64encode(json.dumps(payload).encode("ascii")).decode()
    return paymentheader

def create_header_with_window(valid_after, valid_before, nonce_bytes=None, returnpayload=False):
    if nonce_bytes is None:
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
            "name": USDC_name,
            "version": USDC_version,
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
    payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": CHAINNAME,
        "payload": {
            "signature": sig,
            "authorization": {
                "from": MYADDR,
                "to": payto,
                "value": str(payamount),
                "validAfter": str(typed_data["message"]["validAfter"]),
                "validBefore": str(typed_data["message"]["validBefore"]),
                "nonce": b16e(nonce_bytes),
            },
        },
    }
    if returnpayload:
        return payload
    paymentheader = urlsafe_b64encode(json.dumps(payload).encode("ascii")).decode()
    return paymentheader

payload = create_header(True)
data={
    'x402Version': 1, 
    'paymentPayload': payload, 
    'paymentRequirements': {
        'scheme': 'exact', 
        'network': CHAINNAME, 
        'maxAmountRequired': payload["payload"]["authorization"]["value"], 
        'resource': target.needpay_url, 
        'description': '', 
        'mimeType': '', 
        'outputSchema': {
            'input': {'type': 'http', 'method': 'GET', 'discoverable': True}, 
            'output': None
        }, 
        'payTo': payload["payload"]["authorization"]["to"], 
        'maxTimeoutSeconds': 60,
        'asset': USDC, 
        'extra': {
            'name': USDC_name, 
            'version': USDC_version
        }
    }
}
url = target.facilitator_base.rstrip("/") + "/verify"
# print(f"url: {url}")
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
        from config import ThidWeb_Secret_key
    except Exception as exc:
        raise SystemExit("thirdweb target requires ThidWeb_Secret_key in config.py") from exc
    headers["x-secret-key"] = ThidWeb_Secret_key
    settle_headers["x-secret-key"] = ThidWeb_Secret_key

if "codenut" in target.name:
    SCRIPT_DIR = Path(__file__).resolve().parent 
    CA_PATH = SCRIPT_DIR / "codenut.crt"    
    # sess.verify = str(CA_PATH)
    sess.verify = False








def run(target_name=None):
    import os
    if target_name:
        os.environ["TARGET"] = target_name

    # ### support_test
    _print_step("Correctness Test")
    print(url)
    x = sess.post(url, json=data, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data, x, payload, include_seq=True)
    time.sleep(7 + random.uniform(0, 0.5))
    print(settle_url)
    x = sess.post(settle_url, json=data, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data, x, payload, include_seq=True)


    ### scheme_test
    _print_step("scheme_test")
    print("############ Oracle: verify succeed -> SR1")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    print(url)
    ######################################################
    # sanitized mutations
    #######################################################
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    ## network_test
    _print_step("network_test")
    print("############ Oracle: verify succeed -> SR1")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################

    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    # print(x, x.text)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    ### signature_test1
    _print_step("signature_test")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))


    ### pay_to_test and SR2
    _print_step("pay_to_test")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    ### pay_amount_test
    _print_step("pay_amount_test")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))


    ### insufficient_balance_test
    _print_step("insufficient_balance_testing")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))


    ### expired_validbefore_test
    _print_step("expired_validbefore_test")
    print("############ Oracle: verify succeed -> SR3")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))


    ### tofar_validafter_test
    _print_step("toofar_validafter_test")
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
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))


    ### replay_nonce
    _print_step("replay_nonce, check if settle, check if new block")
    print("############ Oracle: verify succeed -> SR3")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload, include_seq=True)
    time.sleep(2 + random.uniform(0, 0.5))
    # manually check if a new block has been created or reverted

def main():
    run()


if __name__ == "__main__":
    main()
