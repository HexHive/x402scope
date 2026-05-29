from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class TestCase:
    id: str
    description: str
    script: str
    required_features: tuple[str, ...]


TESTS: tuple[TestCase, ...] = (
    TestCase(
        id="evm_verify_settle_base",
        description="EVM verify/settle checks (base)",
        script="verify_settle_base.py",
        required_features=("evm",),
    ),
    TestCase(
        id="evm_verify_settle_base_v2",
        description="EVM verify/settle checks (base v2)",
        script="verify_settle_base_v2.py",
        required_features=("evm","x402v2"),
    ),
    TestCase(
        id="solana_verify_settle",
        description="Solana verify/settle checks",
        script="verify_settle_solana.py",
        required_features=("solana","feepayer"),
    ),
    TestCase(
        id="solana_verify_settle_v2",
        description="Solana verify/settle checks (v2)",
        script="verify_settle_solanav2.py",
        required_features=("solana","x402v2", "feepayer"),
    ),
    TestCase(
        id="evm_6492_test",
        description="EVM 6492 test",
        script="erc6492test.py",
        required_features=("evm",),
    ),
    TestCase(
        id="evm_6492_test_v2",
        description="EVM 6492 test (v2)",
        script="erc6492testv2.py",
        required_features=("evm", "x402v2"),
    ),
    TestCase(
        id="evm_erc1271_test",
        description="EVM ERC-1271 test",
        script="erc1271test.py",
        required_features=("evm",),
    ),
    TestCase(
        id="evm_client_attack",
        description="Client attack scenario (EVM)",
        script="evmclient.py",
        required_features=("evm",),
    ),
)


def filter_tests(available_features: Iterable[str]) -> tuple[TestCase, ...]:
    feature_set = set(available_features)
    return tuple(t for t in TESTS if set(t.required_features).issubset(feature_set))
