############################### Verify-Solana
import os
import sys
import copy
import time
import random
from pathlib import Path

from simplebase import *  
import config
from target import current_target
from oracles import log_verify_result, _print_api_result, tee_run_log

if not hasattr(config, "modify_sol_instructions"):
    config.modify_sol_instructions = lambda instructions, signargs: instructions

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


def _resolve_solana_network(chain_name: str):
    if not chain_name:
        chain_name = "solana-devnet"
    if "devnet" in chain_name:
        return {
            "chain": "solana-devnet",
            "rpc": "https://api.devnet.solana.com",
            "usdc": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
        }
    return {
        "chain": "solana",
        "rpc": "https://api.mainnet-beta.solana.com",
        "usdc": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    }


target = current_target(_resolve_target_name())
chain_cfg = _resolve_solana_network(target.chain_name or target.network)
CHAINNAME = chain_cfg["chain"]
RPC = chain_cfg["rpc"]
USDC = chain_cfg["usdc"]

if not getattr(config, "solpk", None):
    raise SystemExit("Missing config.solpk for Solana payer")

MYADDR = sol_topub(config.solpk)
payto = target.pay_to_address
payamount = target.pay_amount
feepayer = target.feepayer
if not feepayer:
    raise SystemExit("Missing target.feepayer for Solana settle flow")

headers = {}
if "thirdweb" in target.name:
    try:
        headers["x-secret-key"] = config.ThirdWeb_Secret_key
    except Exception as exc:
        raise SystemExit("thirdweb target requires ThirdWeb_Secret_key in config.py") from exc

os.environ.pop("X402_ADDEXTRASIGS", None)

url = target.facilitator_base.rstrip("/") + "/verify"
settle_url = target.settle_url
settle_headers = dict(headers)

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

if "codenut" in target.name:
    SCRIPT_DIR = Path(__file__).resolve().parent
    CA_PATH = SCRIPT_DIR / "codenut.crt"
    # sess.verify = str(CA_PATH)
    sess.verify = False


def _build_solana_payload(pay_to=None, amount=None, payer_pk=None, createata=False, gaslimit=200_000, gasprice=100_000, stx_override=None):
    if pay_to is None:
        pay_to = payto
    if amount is None:
        amount = payamount
    if payer_pk is None:
        payer_pk = config.solpk
    if stx_override is None:
        stx = sol_x402tx(
            RPC,
            USDC,
            payer_pk,
            pay_to,
            amount,
            feepayer,
            createata=createata,
            gaslimit=gaslimit,
            gasprice=gasprice,
            tokendecimals=6,
        )
    else:
        stx = stx_override
    payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": CHAINNAME,
        "payload": {
            "transaction": stx,
        },
    }
    requirements = {
        "scheme": "exact",
        "network": CHAINNAME,
        "maxAmountRequired": str(amount),
        "resource": target.needpay_url,
        "description": "",
        "mimeType": "",
        "outputSchema": {
            "input": {"type": "http", "method": "GET", "discoverable": True},
            "output": None,
        },
        "payTo": pay_to,
        "maxTimeoutSeconds": 60,
        "asset": USDC,
        "extra": {
            "feePayer": feepayer,
            "decimals": 6,
        },
    }
    if "anyspend" in target.name:
        requirements["extra"]["facilitatorAddress"] = feepayer
    return payload, requirements




payment_payload, payment_requirements = _build_solana_payload()
data = {
    "x402Version": 1,
    "paymentPayload": payment_payload,
    "paymentRequirements": payment_requirements,
}




def run(target_name=None):
    import os
    if target_name:
        os.environ["TARGET"] = target_name

    # ### correctness_test
    print("############ 0. Correctness Test")
    print(url)
    x = sess.post(url, json=data, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data, x, payment_payload, include_seq=True, schema="solana")

    print(settle_url)
    x = sess.post(settle_url, json=data, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data, x, payment_payload, include_seq=True, schema="solana")


    ### scheme_test
    print("############ 1. scheme_test")
    print("############ Oracle: verify succeed -> SR1")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    print(url)
    ######################################################
    # sanitized mutations
    #######################################################
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))


    ### network_test
    print("############ 2. network_test")
    print("############ Oracle: verify succeed -> SR1")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))


    ### transaction_test
    print("############ 4. transaction_test")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))


    ### pay_to_test
    print("############ 5. pay_to_test")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))


    ### pay_amount_test
    print("############ 6. pay_amount_test")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))


    ### insufficient_balance_test
    print("############ 7. insufficient_balance_testing")
    print("############ Oracle: verify succeed -> SR1/SR2")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    from solders.keypair import Keypair

    # poor_pk_sol = Keypair().to_base58_string()
    poor_pk_sol=config.poor_pk_sol
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))


    ### ata_missing_test
    print("############ 8. ata_missing_test")
    print("############ Oracle: verify rejected")
    print("############ Oracle: settle rejected")
    poor_pk_sol = config.poor_pk_sol
    poor_addr = sol_topub(poor_pk_sol)
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))


    # high_gas_test
    print("############ 9. high_gas_test_price")
    print("############ Oracle: verify rejected")
    print("############ Oracle: settle rejected")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print("############ 9. high_gas_test_limit")
    print("############ Oracle: verify rejected")
    print("############ Oracle: settle rejected")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))




    ### multi_signer_test
    print("############ 10. multi_signer_test")
    print("############ Oracle: verify rejected")
    print("############ Oracle: settle rejected")
    old_extra = os.environ.get("X402_ADDEXTRASIGS")
    os.environ["X402_ADDEXTRASIGS"] = "8"
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))


    ### replay_transaction
    print("############ 11. replay_transaction, check if settle, check if new block")
    print("############ Oracle: verify succeed -> SR3")
    print("############ Oracle: settle succeed -> SR4, and if verify false -> SR7")
    print("############ Oracle: new block -> SR5, and if verify false -> SR7")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payment_payload, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))



    ### recenthash_test
    print("############ 12. recenthash_test")
    print("############ Oracle: verify rejected")
    print("############ Oracle: settle rejected")
    ######################################################
    # sanitized mutations
    #######################################################
    print(url)
    x = sess.post(url, json=data_mut, headers=headers)
    _print_api_result(x)
    log_verify_result(target, url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

    print(settle_url)
    x = sess.post(settle_url, json=data_mut, headers=settle_headers)
    _print_api_result(x)
    log_verify_result(target, settle_url, headers, data_mut, x, payload_mut, include_seq=True, schema="solana")
    time.sleep(2 + random.uniform(0, 0.5))

def main():
    with tee_run_log(Path(__file__).stem, target.name):
        run()


if __name__ == "__main__":
    main()
