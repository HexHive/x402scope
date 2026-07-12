#!/usr/bin/env python3
"""Generate a Solana keypair for x402scope reviewer tests.

The security test scripts expect Solana private keys in config.py as
base58-encoded strings accepted by solders.keypair.Keypair.from_base58_string().
This helper also writes a Solana CLI-style JSON byte-array key file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path



def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Solana keypair and print the config.py private-key value."
    )
    parser.add_argument(
        "-o",
        "--output",
        default="solana-server.json",
        help="path for Solana CLI-style JSON key file (default: solana-server.json)",
    )
    args = parser.parse_args()

    try:
        from solders.keypair import Keypair
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency: solders. Install requirements first with: pip install -r requirements.txt"
        ) from exc

    kp = Keypair()
    output_path = Path(args.output)
    output_path.write_text(json.dumps(list(bytes(kp))))

    print("Solana address:", kp.pubkey())
    print("Private key for config.py:", str(kp))
    print("Private key also saved to", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
