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
    parent = os.path.dirname(csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


class _TeeStream:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
        self.flush()
        return len(data)

    def flush(self):
        for stream in self.streams:
            stream.flush()

    def isatty(self):
        return any(getattr(stream, "isatty", lambda: False)() for stream in self.streams)


def _safe_log_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)


class TeeRunLog:
    def __init__(self, script_name: str, target_name: str | None = None, log_dir: str | None = None):
        self.script_name = _safe_log_name(script_name)
        self.target_name = _safe_log_name(target_name or "unknown-target")
        self.log_dir = log_dir or os.path.join(os.path.dirname(__file__), "..", "expdata", "run_logs")
        self.started_at = dt.datetime.now().astimezone()
        stamp = self.started_at.strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.abspath(os.path.join(self.log_dir, f"{stamp}_{self.script_name}_{self.target_name}.log"))
        self._file = None
        self._old_stdout = None
        self._old_stderr = None

    def __enter__(self):
        import sys

        os.makedirs(self.log_dir, exist_ok=True)
        self._file = open(self.log_path, "a", encoding="utf-8", buffering=1)
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        sys.stdout = _TeeStream(self._old_stdout, self._file)
        sys.stderr = _TeeStream(self._old_stderr, self._file)
        print(f"[run-log] started_at: {self.started_at.isoformat(timespec='seconds')}")
        print(f"[run-log] script: {self.script_name}")
        print(f"[run-log] target: {self.target_name}")
        print(f"[run-log] saving terminal output to: {self.log_path}")
        return self

    def __exit__(self, exc_type, exc, tb):
        import sys

        finished_at = dt.datetime.now().astimezone()
        try:
            print(f"[run-log] finished_at: {finished_at.isoformat(timespec='seconds')}")
            if exc_type is not None:
                print(f"[run-log] exited_with: {exc_type.__name__}: {exc}")
        finally:
            sys.stdout = self._old_stdout
            sys.stderr = self._old_stderr
            if self._file:
                self._file.close()
        return False


def tee_run_log(script_name: str, target_name: str | None = None, log_dir: str | None = None) -> TeeRunLog:
    return TeeRunLog(script_name, target_name, log_dir)


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
    print(f"HTTP {response.status_code}")
    try:
        data = response.json()
    except Exception:
        print(f"response: {response.text}")
        return
    if not isinstance(data, dict):
        print(f"response: {json.dumps(data, ensure_ascii=False)}")
        return

    is_valid = data.get("isValid")
    reason = data.get("invalidReason") or data.get("errorReason") or data.get("reason")
    success = data.get("success")
    printed = False
    if is_valid is not None:
        print(f"isValid: {is_valid}")
        printed = True
    if reason:
        print(f"reason: {reason}")
        printed = True
    if success is not None:
        print(f"success: {success}")
        printed = True
        if success:
            tx = data.get("transaction")
            if tx is None:
                tx = data.get("tx")
            if tx is not None:
                print(f"transaction: {tx}")

    # Some facilitators return a valid JSON body without the standard x402
    # result fields. Keep those responses visible instead of failing silently.
    if not printed:
        print(f"response: {json.dumps(data, ensure_ascii=False)}")
