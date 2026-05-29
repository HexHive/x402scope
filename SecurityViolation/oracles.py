from __future__ import annotations

import csv
import datetime as dt
import json
import os


LOG_SEQ = 0


def _log_seq() -> int:
    global LOG_SEQ
    LOG_SEQ += 1
    return LOG_SEQ


def _append_csv_result(csv_path, row, fieldnames):
    write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def log_verify_result(
    target,
    url,
    headers,
    data,
    response,
    payload,
    csv_path=None,
    include_seq: bool = False,
    schema: str = "evm",
):
    timestamp = dt.datetime.now().isoformat(timespec="seconds")
    payload_auth = payload.get("payload", {}).get("authorization", {})
    payment_req = data.get("paymentRequirements", {}) if isinstance(data, dict) else {}
    payload_tx = payload.get("payload", {}).get("transaction", "")

    row = {
        "timestamp": timestamp,
        "target_name": target.name,
        "target_network": target.network,
        "raw_url": url,
        "raw_request_headers": json.dumps(headers, ensure_ascii=True),
        "raw_request_body": json.dumps(data, ensure_ascii=True),
        "raw_response_status": response.status_code,
        "raw_response_headers": json.dumps(dict(response.headers), ensure_ascii=True),
        "raw_response_body": response.text,
        "test_result": "success" if response.ok else "failed",
    }

    if schema == "solana":
        pay_value = payment_req.get("maxAmountRequired", payment_req.get("amount", ""))
        row.update(
            {
                "pay_from": "",
                "pay_to": payment_req.get("payTo", ""),
                "pay_value": pay_value,
                "valid_after": "",
                "valid_before": "",
                "nonce": "",
                "transaction": payload_tx,
            }
        )
        csv_fields = [
            "timestamp",
            "target_name",
            "target_network",
            "raw_url",
            "raw_request_headers",
            "raw_request_body",
            "raw_response_status",
            "raw_response_headers",
            "raw_response_body",
            "pay_from",
            "pay_to",
            "pay_value",
            "valid_after",
            "valid_before",
            "nonce",
            "transaction",
            "test_result",
        ]
        if not csv_path:
            csv_filename = f"../expdata/{target.name}_verify_results_solana.csv"
            csv_path = os.path.join(os.path.dirname(__file__), csv_filename)
    else:
        row.update(
            {
                "pay_from": payload_auth.get("from", ""),
                "pay_to": payload_auth.get("to", ""),
                "pay_value": payload_auth.get("value", ""),
                "valid_after": payload_auth.get("validAfter", ""),
                "valid_before": payload_auth.get("validBefore", ""),
                "nonce": payload_auth.get("nonce", ""),
            }
        )
        csv_fields = [
            "timestamp",
            "target_name",
            "target_network",
            "raw_url",
            "raw_request_headers",
            "raw_request_body",
            "raw_response_status",
            "raw_response_headers",
            "raw_response_body",
            "pay_from",
            "pay_to",
            "pay_value",
            "valid_after",
            "valid_before",
            "nonce",
            "test_result",
        ]
        if not csv_path:
            csv_filename = f"../expdata/{target.name}_verify_results.csv"
            csv_path = os.path.join(os.path.dirname(__file__), csv_filename)

    if include_seq:
        row["seq"] = _log_seq()
        csv_fields = ["seq"] + csv_fields

    _append_csv_result(csv_path, row, csv_fields)


def _print_api_result(response):
    try:
        data = response.json()
    except Exception:
        print(response, response.text)
        return
    is_valid = data.get("isValid")
    reason = data.get("invalidReason") or data.get("errorReason") or data.get("reason")
    success = data.get("success")
    if is_valid is not None:
        print(f"isValid: {is_valid}")
    if reason:
        print(f"reason: {reason}")
    if success is not None:
        print(f"success: {success}")
        if success:
            tx = data.get("transaction")
            if tx is None:
                tx = data.get("tx")
            if tx is not None:
                print(f"transaction: {tx}")
