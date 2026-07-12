#!/usr/bin/env python3
"""Deploy the Basefee-only ERC-1271 helper contract.

Example:
    OWNER_PK=0x... python3 SecurityViolation/Scripts/deploy_erc1271_basefee.py \
        --network base-sepolia

After deployment, run the ERC-1271 v2 test with:
    CONTRACT=<deployed_address> python3 SecurityViolation/erc1271testv2.py -t coinbase-test
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from web3 import Web3
from eth_utils import keccak

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SECURITY_DIR = REPO_ROOT / "SecurityViolation"
DEFAULT_SOURCE = SECURITY_DIR / "HelperContracts" / "Attackx402BasefeeOnly.sol"

NETWORKS = {
    "base-sepolia": {
        "rpc": "https://sepolia.base.org",
        "chain_id": 84532,
        "test_command": "CONTRACT={addr} python3 SecurityViolation/erc1271testv2.py -t coinbase-test",
    },
    "base": {
        "rpc": "https://mainnet.base.org",
        "chain_id": 8453,
        "test_command": "CONTRACT={addr} python3 SecurityViolation/erc1271testv2.py -t coinbase-main",
    },
}



def _private_key_from_config() -> str | None:
    """Read local SecurityViolation/config.py if available.

    config.example.py intentionally contains blanks, so deployment can only use
    the operator's private local config.py.
    """
    sys.path.insert(0, str(SECURITY_DIR))
    try:
        import config  # type: ignore
    except Exception:
        return None
    for name in ("pk1", "privatekey"):
        value = getattr(config, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None

def _compile_with_solcx(source_path: Path, solc_version: str) -> tuple[list[dict[str, Any]], str]:
    try:
        import solcx  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("py-solc-x is not installed") from exc

    installed = {str(v) for v in solcx.get_installed_solc_versions()}
    if solc_version not in installed:
        print(f"Installing solc {solc_version} via py-solc-x...")
        solcx.install_solc(solc_version)
    solcx.set_solc_version(solc_version)

    source = source_path.read_text()
    compiled = solcx.compile_standard(
        {
            "language": "Solidity",
            "sources": {source_path.name: {"content": source}},
            "settings": {
                "optimizer": {"enabled": True, "runs": 200},
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
            },
        }
    )
    contract = compiled["contracts"][source_path.name]["Attackx402BasefeeOnly"]
    abi = contract["abi"]
    bytecode = contract["evm"]["bytecode"]["object"]
    return abi, bytecode


def _compile_with_solc_binary(source_path: Path) -> tuple[list[dict[str, Any]], str]:
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        cmd = [
            "solc",
            "--optimize",
            "--combined-json",
            "abi,bin",
            str(source_path),
        ]
        proc = subprocess.run(cmd, check=True, text=True, capture_output=True)
        data = json.loads(proc.stdout)
    key = next(k for k in data["contracts"] if k.endswith(":Attackx402BasefeeOnly"))
    contract = data["contracts"][key]
    abi = json.loads(contract["abi"]) if isinstance(contract["abi"], str) else contract["abi"]
    bytecode = contract["bin"]
    return abi, bytecode


def compile_contract(source_path: Path, solc_version: str) -> tuple[list[dict[str, Any]], str]:
    try:
        return _compile_with_solcx(source_path, solc_version)
    except Exception as solcx_exc:
        try:
            return _compile_with_solc_binary(source_path)
        except Exception as solc_exc:
            raise SystemExit(
                "Could not compile Solidity contract. Install one of:\n"
                "  pip install py-solc-x\n"
                "or install a solc binary on PATH.\n"
                f"py-solc-x error: {solcx_exc}\n"
                f"solc error: {solc_exc}"
            )


def build_fee_tx(w3: Web3, tx: dict[str, Any]) -> dict[str, Any]:
    latest = w3.eth.get_block("latest")
    if "baseFeePerGas" in latest:
        priority = w3.to_wei(0.01, "gwei")
        tx["maxPriorityFeePerGas"] = priority
        tx["maxFeePerGas"] = int(latest["baseFeePerGas"] * 2 + priority)
    else:
        tx["gasPrice"] = w3.eth.gas_price
    return tx


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Attackx402BasefeeOnly")
    parser.add_argument("--network", choices=NETWORKS, default="base-sepolia")
    parser.add_argument("--rpc", help="override RPC URL")
    parser.add_argument(
        "--private-key",
        default=os.getenv("OWNER_PK") or os.getenv("PRIVATE_KEY") or _private_key_from_config(),
        help="deployer private key; defaults to OWNER_PK/PRIVATE_KEY or local SecurityViolation/config.py pk1",
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--solc-version", default="0.8.25")
    args = parser.parse_args()

    if not args.private_key:
        raise SystemExit(
            "Missing deployer private key. Use --private-key, OWNER_PK/PRIVATE_KEY, "
            "or set pk1 in local SecurityViolation/config.py."
        )

    net = NETWORKS[args.network]
    rpc = args.rpc or net["rpc"]
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        raise SystemExit(f"Could not connect to RPC: {rpc}")

    chain_id = w3.eth.chain_id
    if chain_id != net["chain_id"]:
        raise SystemExit(f"RPC chain id mismatch: got {chain_id}, expected {net['chain_id']}")

    acct = w3.eth.account.from_key(args.private_key)
    print("network:", args.network)
    print("rpc:", rpc)
    print("deployer:", acct.address)
    print("balance ETH:", w3.from_wei(w3.eth.get_balance(acct.address), "ether"))

    abi, bytecode = compile_contract(args.source, args.solc_version)
    print("bytecode bytes:", len(bytecode) // 2)
    print("bytecode hash:", keccak(bytes.fromhex(bytecode)).hex())

    contract = w3.eth.contract(abi=abi, bytecode="0x" + bytecode)
    tx = contract.constructor().build_transaction(
        {
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "chainId": chain_id,
        }
    )
    tx = build_fee_tx(w3, tx)
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.3)

    signed = acct.sign_transaction(tx)
    raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    print("deploy tx:", tx_hash.hex())
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("receipt status:", receipt.status)
    if receipt.status != 1:
        raise SystemExit("Deployment reverted")
    addr = receipt.contractAddress
    print("contract:", addr)
    code = w3.eth.get_code(addr)
    print("runtime bytes:", len(code))
    print("runtime hash:", keccak(bytes(code)).hex())
    print("\nNext test command:")
    print(net["test_command"].format(addr=addr))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
