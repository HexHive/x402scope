#!/usr/bin/env python3
"""Minimal local merchant server for x402 v2 EVM client-flow tests.

This avoids the legacy x402 Flask middleware path and sends v2-shaped
/verify and /settle requests directly to the configured facilitator.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from base64 import urlsafe_b64decode

import requests
from flask import Flask, jsonify, make_response, request

import config
from target import current_target


def _resolve_target_name_from_cli() -> str | None:
    for flag in ("-t", "--target"):
        if flag in sys.argv:
            idx = sys.argv.index(flag)
            try:
                return sys.argv[idx + 1]
            except IndexError as exc:
                raise SystemExit("Missing target name after -t/--target") from exc
    return None


def _coinbase_endpoint_and_headers(action: str):
    from cdp.x402 import create_facilitator_config

    facilitator_config = create_facilitator_config(
        api_key_id=config.CDP_API_KEY_ID,
        api_key_secret=config.CDP_API_KEY_SECRET,
    )
    headers = asyncio.run(facilitator_config["create_headers"]())[action]
    return facilitator_config["url"] + "/" + action, headers


def _endpoint_and_headers(action: str):
    headers = {"Content-Type": "application/json"}
    if "coinbase" in target.name:
        url, auth_headers = _coinbase_endpoint_and_headers(action)
        headers.update(auth_headers)
        return url, headers
    if "thirdweb" in target.name:
        headers["x-secret-key"] = config.ThirdWeb_Secret_key
    return target.facilitator_base.rstrip("/") + "/" + action, headers


def _decode_payment_header(value: str) -> dict:
    padded = value + "=" * (-len(value) % 4)
    return json.loads(urlsafe_b64decode(padded.encode()).decode())


def _is_valid_verify_response(resp: requests.Response) -> bool:
    if not resp.ok:
        return False
    try:
        data = resp.json()
    except Exception:
        return False
    if "isValid" in data:
        return bool(data.get("isValid"))
    if "valid" in data:
        return bool(data.get("valid"))
    return False


target = current_target(_resolve_target_name_from_cli())
NEEDPAY_PATH = target.needpay_path if target.needpay_path.startswith("/") else f"/{target.needpay_path}"

app = Flask(__name__)


@app.get(NEEDPAY_PATH)
def view_needpay():
    payment_header = request.headers.get("X-Payment") or request.headers.get("X-PAYMENT")
    if not payment_header:
        return jsonify({"error": "No X-Payment header provided"}), 402

    try:
        payment_payload = _decode_payment_header(payment_header)
    except Exception as exc:
        return jsonify({"error": f"Invalid X-Payment header: {exc}"}), 402

    payment_requirements = payment_payload.get("accepted")
    if not payment_requirements:
        return jsonify({"error": "Missing v2 accepted payment requirements"}), 402

    data = {
        "x402Version": 2,
        "paymentPayload": payment_payload,
        "paymentRequirements": payment_requirements,
    }

    verify_url, verify_headers = _endpoint_and_headers("verify")
    verify_resp = requests.post(verify_url, json=data, headers=verify_headers, timeout=30)
    print("verify:", verify_resp.status_code, verify_resp.text)
    if not _is_valid_verify_response(verify_resp):
        return jsonify({"error": "Invalid payment", "verifyResponse": _safe_json(verify_resp)}), 402

    settle_url, settle_headers = _endpoint_and_headers("settle")
    settle_resp = requests.post(settle_url, json=data, headers=settle_headers, timeout=30)
    print("settle:", settle_resp.status_code, settle_resp.text)

    # Mirror the legacy x402 middleware behavior used by server_app.py: once
    # /verify succeeds and the protected resource returns a 2xx response, a
    # settlement failure is logged but does not retroactively deny the content.
    # This is intentional for SR4/SR7-style client-flow tests such as
    # erc1271testv2.py, where verify may succeed but settle should fail.
    settle_data = _safe_json(settle_resp)
    settle_ok = False
    if settle_resp.ok and isinstance(settle_data, dict):
        if "success" in settle_data:
            settle_ok = bool(settle_data.get("success"))
        elif settle_data.get("transaction") or settle_data.get("tx"):
            settle_ok = True
    if not settle_ok:
        print("Settle failed but returning protected content after successful verify")

    resp = make_response("paid content")
    resp.headers["X-Settle-Status"] = "success" if settle_ok else "failed"
    return resp


def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text


def run(target_name=None):
    if target_name:
        os.environ["TARGET"] = target_name
    app.run(host="0.0.0.0", port=8001, debug=True)


def main():
    run()


if __name__ == "__main__":
    main()
