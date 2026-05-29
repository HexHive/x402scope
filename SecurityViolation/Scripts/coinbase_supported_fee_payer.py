import os
import sys
import json
import requests
import asyncio

import config
from cdp.x402 import create_facilitator_config
from cdp.auth.utils.http import GetAuthHeadersOptions, get_auth_headers


def main() -> int:
    facilitator_config = create_facilitator_config(
        api_key_id=getattr(config, "CDP_API_KEY_ID", None),
        api_key_secret=getattr(config, "CDP_API_KEY_SECRET", None),
    )
    base_url = os.getenv("COINBASE_X402_BASE", "https://api.cdp.coinbase.com/platform/v2/x402/")
    url = base_url.rstrip("/") + "/supported"
    headers = {}
    api_key_id = getattr(config, "CDP_API_KEY_ID", None)
    api_key_secret = getattr(config, "CDP_API_KEY_SECRET", None)
    if api_key_id and api_key_secret:
        headers.update(
            get_auth_headers(
                GetAuthHeadersOptions(
                    api_key_id=api_key_id,
                    api_key_secret=api_key_secret,
                    request_method="GET",
                    request_host="api.cdp.coinbase.com",
                    request_path="/platform/v2/x402/supported",
                    source="x402",
                    source_version="0.6.1",
                )
            )
        )
    else:
        try:
            hdrs = asyncio.run(facilitator_config["create_headers"]())
            if isinstance(hdrs, dict):
                if "list" in hdrs:
                    headers.update(hdrs["list"])
                else:
                    headers.update(hdrs)
        except Exception as exc:
            print(f"warning: failed to build auth headers: {exc}")
    try:
        resp = requests.get(url, headers=headers, timeout=20)
    except Exception as exc:
        print(f"request failed: {exc}")
        return 1
    print("status:", resp.status_code)
    try:
        data = resp.json()
    except Exception:
        print(resp.text)
        return 1

    kinds = data.get("kinds", [])
    fee_payers = []
    for item in kinds:
        extra = item.get("extra", {}) or {}
        fee = extra.get("feePayer")
        if fee:
            fee_payers.append(
                {
                    "x402Version": item.get("x402Version"),
                    "scheme": item.get("scheme"),
                    "network": item.get("network"),
                    "feePayer": fee,
                }
            )

    print("feePayer entries:")
    print(json.dumps(fee_payers, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
