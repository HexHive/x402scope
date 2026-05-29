#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import importlib
import runpy
import subprocess
import sys
import time
from pathlib import Path

from tests import TESTS, filter_tests
from target import current_target


SCRIPT_DIR = Path(__file__).resolve().parent


def probe_features(target, base_support_ok: bool) -> list[str]:
    features: list[str] = []

    chain_name = (getattr(target, "chain_name", "") or "").lower()
    network = (getattr(target, "network", "") or "").lower()
    name = (getattr(target, "name", "") or "").lower()

    if "solana" in chain_name or "solana" in network or "solana" in name:
        features.append("solana")
    if base_support_ok:
        features.append("evm")

    if getattr(target, "feepayer", None):
        features.append("feepayer")
    if "coinbase" in name:
        features.append("coinbase")
    if "thirdweb" in name:
        features.append("thirdweb")

    return features


def run_script(script: str, target_name: str) -> dict:
    if script == "evmclient.py":
        return run_script_with_server(script, target_name, "server_app.py")

    path = SCRIPT_DIR / script
    if not path.exists():
        return {
            "returncode": 2,
            "stdout": "",
            "stderr": f"Missing script: {path}",
            "duration": 0.0,
        }

    return run_script_inprocess(path, target_name)


def run_script_inprocess(path: Path, target_name: str) -> dict:
    start = time.time()
    old_argv = sys.argv[:]
    old_env = os.environ.copy()
    old_sys_path = sys.path[:]
    returncode = 0
    try:
        os.environ["TARGET"] = target_name
        sys.argv = [str(path), "-t", target_name]
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            module_name = path.stem
            module = importlib.import_module(module_name)
            module = importlib.reload(module)
            if hasattr(module, "run") and callable(getattr(module, "run")):
                module.run(target_name)
            elif hasattr(module, "main") and callable(getattr(module, "main")):
                module.main()
            else:
                runpy.run_path(str(path), run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            returncode = 0 if code is None else int(code)
    except Exception as exc:
        returncode = 1
        print(f"Exception: {exc}", file=sys.stderr)
    finally:
        sys.argv = old_argv
        os.environ.clear()
        os.environ.update(old_env)
        sys.path = old_sys_path
    duration = time.time() - start
    return {
        "returncode": returncode,
        "stdout": "",
        "stderr": "",
        "duration": duration,
    }


def run_script_with_server(client_script: str, target_name: str, server_script: str) -> dict:
    server_path = SCRIPT_DIR / server_script
    client_path = SCRIPT_DIR / client_script
    if not server_path.exists():
        return {
            "returncode": 2,
            "stdout": "",
            "stderr": f"Missing server script: {server_path}",
            "duration": 0.0,
        }

    if not client_path.exists():
        return {
            "returncode": 2,
            "stdout": "",
            "stderr": f"Missing client script: {client_path}",
            "duration": 0.0,
        }

    server_cmd = [sys.executable, str(server_path), "-t", target_name]

    server_proc = subprocess.Popen(server_cmd)
    try:
        time.sleep(2.0)
        return run_script_inprocess(client_path, target_name)
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()


def _patch_target_content(content: str, target_name: str, pay_amount: int, valid_before_offset: int) -> str:
    double_key = f"\"{target_name}\": FacilitatorTarget("
    single_key = f"'{target_name}': FacilitatorTarget("
    start = content.find(double_key)
    if start == -1:
        start = content.find(single_key)
    if start == -1:
        raise ValueError(f"Target '{target_name}' not found in target.py")

    block_end = content.find("\n    ),", start)
    if block_end == -1:
        raise ValueError(f"Failed to locate end of target '{target_name}' block")
    block_end += len("\n    ),")
    block = content[start:block_end]

    def _replace_or_insert(block_text: str, key: str, value: int) -> str:
        pattern = rf"(^\s*{re.escape(key)}\s*=\s*.*$)"
        replacement = f"        {key}={value},"
        new_text, count = re.subn(pattern, replacement, block_text, flags=re.MULTILINE)
        if count > 0:
            return new_text
        insert_at = block_text.rfind("\n    ),")
        if insert_at == -1:
            raise ValueError("Malformed target block; missing closing '),'.")
        return block_text[:insert_at] + f"\n        {key}={value}," + block_text[insert_at:]

    block = _replace_or_insert(block, "pay_amount", pay_amount)
    block = _replace_or_insert(block, "valid_before_offset", valid_before_offset)

    return content[:start] + block + content[block_end:]


def _extract_valid_before_offset(content: str, target_name: str) -> int:
    double_key = f"\"{target_name}\": FacilitatorTarget("
    single_key = f"'{target_name}': FacilitatorTarget("
    start = content.find(double_key)
    if start == -1:
        start = content.find(single_key)
    if start == -1:
        raise ValueError(f"Target '{target_name}' not found in target.py")

    block_end = content.find("\n    ),", start)
    if block_end == -1:
        raise ValueError(f"Failed to locate end of target '{target_name}' block")
    block_end += len("\n    ),")
    block = content[start:block_end]

    match = re.search(r"^\s*valid_before_offset\s*=\s*([0-9]+)\s*,", block, flags=re.MULTILINE)
    if match:
        return int(match.group(1))
    # Fallback to a safe default if not specified
    return 7


def run_base_support_matrix(target_name: str) -> list[dict]:
    target_path = SCRIPT_DIR / "target.py"
    original = target_path.read_text()
    results: list[dict] = []

    try:
        # First: pay_amount=0 with current valid_before_offset (keep as-is)
        current_vb = _extract_valid_before_offset(original, target_name)
        patched_zero = _patch_target_content(
            original,
            target_name=target_name,
            pay_amount=0,
            valid_before_offset=current_vb,
        )
        target_path.write_text(patched_zero)
        result_zero = run_script("basesupport.py", target_name)
        result_zero["pay_amount"] = 0
        result_zero["valid_before_offset"] = current_vb
        results.append(result_zero)

        # Then: pay_amount=0, valid_before_offset=1..10; stop at first success
        for valid_before in range(1, 11):
            patched = _patch_target_content(
                original,
                target_name=target_name,
                pay_amount=0,
                valid_before_offset=valid_before,
            )
            target_path.write_text(patched)
            result = run_script("basesupport.py", target_name)
            result["pay_amount"] = 0
            result["valid_before_offset"] = valid_before
            results.append(result)
            if result.get("returncode", 1) == 0:
                break
    finally:
        target_path.write_text(original)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run security rule-violation tests by target.")
    parser.add_argument("-t", "--target", required=True, help="target name from target.py")
    parser.add_argument("--list", action="store_true", help="list available tests")
    parser.add_argument("--tests", help="comma-separated test ids to run")
    parser.add_argument("--support-matrix", action="store_true", help="run basesupport pay_amount=0 matrix")
    args = parser.parse_args()

    if args.list:
        for t in TESTS:
            print(f"{t.id}: {t.description}  (requires: {', '.join(t.required_features)})")
        return 0

    target = current_target(args.target)
    chain_name = (getattr(target, "chain_name", "") or "").lower()
    network = (getattr(target, "network", "") or "").lower()
    name = (getattr(target, "name", "") or "").lower()
    is_solana = "solana" in chain_name or "solana" in network or "solana" in name

    base_support_ok = False
    if not is_solana:
        base_support_result = run_script("basesupport.py", args.target)
        base_support_ok = base_support_result.get("returncode", 1) == 0
        verdict = "pass" if base_support_ok else "fail"
        print(f"basesupport.py: {verdict}")
        if not base_support_ok:
            print(base_support_result.get("stderr") or base_support_result.get("stdout") or "")

    features = probe_features(target, base_support_ok)

    if args.tests:
        wanted = {x.strip() for x in args.tests.split(",") if x.strip()}
        selected = [t for t in TESTS if t.id in wanted]
    else:
        selected = list(filter_tests(features))

    if not selected:
        print("No tests selected.")
        return 1

    print(f"Target: {args.target}")
    print(f"Features: {', '.join(features)}")
    print("")

    exit_code = 0
    if base_support_ok and args.support_matrix:
        print("==> basesupport matrix: pay_amount=0, then valid_before_offset=1..10 (stop on first success)")
        matrix_results = run_base_support_matrix(args.target)
        for idx, res in enumerate(matrix_results):
            ok = res.get("returncode", 1) == 0
            status = "pass" if ok else "fail"
            vb = res.get("valid_before_offset")
            if idx == 0:
                print(f"pay_amount=0 (current valid_before_offset): {status}")
            else:
                print(f"valid_before_offset={vb}: {status}")
            if not ok:
                exit_code = 1
        print("")

    for test in selected:
        print(f"==> {test.id}: {test.description}")
        run_script(test.script, args.target)
        print("")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
