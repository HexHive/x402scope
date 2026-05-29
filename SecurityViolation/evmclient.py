import os
import sys
import secrets

import config
from simplebase import *
from target import current_target
from config import pk1,pk2

#### SR4/SR7
def _resolve_target_name() -> str:
    """
    Require an explicit target: via CLI (-t/--target or first positional) or TARGET env.
    We no longer accept the legacy 'test' shortcut; use target.py to set chain_name.
    """
    for flag in ("-t", "--target"):
        if flag in sys.argv:
            idx = sys.argv.index(flag)
            try:
                return sys.argv[idx + 1]
            except IndexError as exc:
                raise SystemExit("Missing target name after -t/--target") from exc
    if len(sys.argv) > 1:
        return sys.argv[1]
    env_target = os.getenv("TARGET")
    if env_target:
        return env_target
    raise SystemExit("Please specify a target via -t/--target, positional arg, or TARGET env")


# Chain presets keyed by network name
CHAIN_PRESETS = {
    "base": {
        "chainid": 8453,
        "name": "base",
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "usdc_version": "2",
        "usdc_name": "USD Coin",
        "endpoints": [
            "https://mainnet.base.org",
            "https://base.public.blockpi.network/v1/rpc/public",
            "https://base-rpc.publicnode.com",
        ],
    },
    "base-sepolia": {
        "chainid": 84532,
        "name": "base-sepolia",
        "usdc": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "usdc_version": "2",
        "usdc_name": "USDC",
        "endpoints": [
            "https://base-sepolia.drpc.org",
            "https://sepolia.base.org",
            "https://base-sepolia-rpc.publicnode.com",
        ],
    },
}

# Require explicit target selection (CLI or env)
target = current_target(_resolve_target_name())
# Use one source of truth for network/chain selection
chain_key = target.network
if chain_key not in CHAIN_PRESETS:
    raise ValueError(f"Unsupported chain_name '{chain_key}'. Known: {', '.join(CHAIN_PRESETS)}")
chain_cfg = CHAIN_PRESETS[chain_key]

chainid = chain_cfg["chainid"]
CHAINNAME = target.network  # network in header must match server requirements
USDC = chain_cfg["usdc"]
USDC_version = chain_cfg["usdc_version"]
USDC_name = chain_cfg["usdc_name"]
p = Endpoint_Provider(chain_cfg["endpoints"])

# when testing testnet, we are using 0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A pk = '1'*64
testnet_pk = "1" * 64  # addr 0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A
use_testnet_key = chain_key.endswith("sepolia")
pk = testnet_pk if use_testnet_key else pk1
config.privatekey = pk  # keep simplebase helpers aligned
MYADDR = topub(pk)
payto = target.pay_to_address or topub(pk2)
payamount = target.pay_amount
url = target.needpay_url

def create_header():
    ts = int(time.time())
    valid_after, valid_before = target.auth_window(ts)
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
            "name": USDC_name,
            "version": USDC_version,
            "chainId": chainid,
            "verifyingContract": USDC,
        },
        "message": {
            "from": MYADDR,
            "to": payto,
            "value": payamount,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce_bytes,
        },
    }
    sig = sign_eip712(typed_data, pk)
    paymentheader = urlsafe_b64encode(json.dumps({
        "x402Version":1,
        "scheme":"exact",
        "network":CHAINNAME,
        "payload":{
            "signature":sig,
            "authorization":{
                "from":MYADDR,
                "to":payto,
                "value":str(payamount),
                "validAfter":str(typed_data["message"]["validAfter"]),
                "validBefore":str(typed_data["message"]["validBefore"]),
                "nonce":b16e(nonce_bytes)
            }
        }
    }).encode("ascii")).decode()
    print("paymentheader: ")
    print(paymentheader)
    return paymentheader

def run(target_name=None):
    import os
    if target_name:
        os.environ["TARGET"] = target_name

    #multi sending
    # Fetch USDC balance of the payer address on the selected network
    bal = p.erc20_balanceOf(USDC, MYADDR)
    # Print human-readable balance (USDC has 6 decimals)
    print(f"MYADDR: {MYADDR}")
    print(f"MY Balance: {bal/1e6}")
    assert bal>payamount
    import threading
    def go(name, paymentheader):
        x = getsess().get(url, headers={"X-Payment": paymentheader})
        req = x.request   
        print(name, x, x.headers)
        if x.status_code!=200:
            print(name, x.text)

    # Create one payment header using EIP721 signature (reused across all threads here. Use 1 to test if supports)
    paymentheader = create_header()
    ths = []
    for i in range(1): 
        t = threading.Thread(target=go, args=[f"{i}", paymentheader])
        ths.append(t)
    [i.start() for i in ths]
    [i.join() for i in ths]

def main():
    run()


if __name__ == "__main__":
    main()
