import json
from typing import Any

from simplebase import sess
from target import FACILITATORS


def _normalize_base(url: str) -> str:
    return url.rstrip("/")


def _extract_networks(payload: Any) -> tuple[list[str], list[str]]:
    networks = set()
    feepayers = set()

    def _collect(obj: Any) -> None:
        if isinstance(obj, dict):
            if "network" in obj and isinstance(obj["network"], str):
                networks.add(obj["network"])
            for key in ("feePayer", "feepayer", "fee_payer"):
                value = obj.get(key)
                if isinstance(value, str) and value:
                    feepayers.add(value)
            for value in obj.values():
                _collect(value)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(payload)
    return sorted(networks), sorted(feepayers)


def _build_request(base: str) -> tuple[str, dict[str, str]]:
    headers: dict[str, str] = {}
    url = f"{base}/supported"

    if "api.cdp.coinbase.com" in base:
        from config import CDP_API_KEY_ID, CDP_API_KEY_SECRET
        from cdp.auth.utils.http import GetAuthHeadersOptions, get_auth_headers
        from cdp.x402.x402 import (
            COINBASE_FACILITATOR_BASE_URL,
            COINBASE_FACILITATOR_V2_ROUTE,
            X402_VERSION,
        )

        if not CDP_API_KEY_ID or not CDP_API_KEY_SECRET:
            raise RuntimeError("missing CDP_API_KEY_ID/CDP_API_KEY_SECRET in config.py")

        url = f"{COINBASE_FACILITATOR_BASE_URL}{COINBASE_FACILITATOR_V2_ROUTE}/supported"
        request_host = COINBASE_FACILITATOR_BASE_URL.replace("https://", "")
        request_path = f"{COINBASE_FACILITATOR_V2_ROUTE}/supported"
        headers = get_auth_headers(
            GetAuthHeadersOptions(
                api_key_id=CDP_API_KEY_ID,
                api_key_secret=CDP_API_KEY_SECRET,
                request_host=request_host,
                request_path=request_path,
                request_method="GET",
                source="x402",
                source_version=X402_VERSION,
            )
        )

    if "api.thirdweb.com" in base:
        try:
            from config import ThidWeb_Secret_key
        except Exception:
            ThidWeb_Secret_key = ""
        if ThidWeb_Secret_key:
            headers["x-secret-key"] = ThidWeb_Secret_key

    return url, headers


def main() -> None:
    grouped: dict[str, list[str]] = {}
    for key, target in FACILITATORS.items():
        base = _normalize_base(target.facilitator_base)
        grouped.setdefault(base, []).append(key)

    for base, keys in sorted(grouped.items()):
        print(f"\nFACILITATOR: {base}")
        print(f"targets: {', '.join(sorted(keys))}")
        try:
            url, headers = _build_request(base)
        except Exception as exc:
            print(f"error: {exc}")
            continue

        try:
            resp = sess.get(url, headers=headers, timeout=15)
        except Exception as exc:
            print(f"request failed: {exc}")
            continue

        print(f"status: {resp.status_code}")
        try:
            payload = resp.json()
        except Exception:
            print(resp.text)
            continue

        networks, feepayers = _extract_networks(payload)
        if networks:
            print("networks:", ", ".join(networks))
        else:
            print("networks: (none detected)")
            print("raw:", json.dumps(payload, ensure_ascii=True)[:1000])

        if feepayers:
            print("feepayer:", ", ".join(feepayers))


if __name__ == "__main__":
    main()
