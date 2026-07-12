import os,sys,time
from flask import Flask, jsonify
from dotenv import load_dotenv
from x402.flask.middleware import PaymentMiddleware
from x402.types import EIP712Domain, TokenAmount, TokenAsset
from x402.facilitator import FacilitatorConfig
from target import current_target
import config


# --- Facilitator configuration ---

def _resolve_target_name_from_cli() -> str | None:
    """Support `python3 server_app.py -t openx402` style selection."""
    for flag in ("-t", "--target"):
        if flag in sys.argv:
            idx = sys.argv.index(flag)
            try:
                return sys.argv[idx + 1]
            except IndexError as exc:
                raise SystemExit("Missing target name after -t/--target") from exc
    return None


def _build_facilitator_config(target):
    # Special handling for Coinbase CDP facilitator (needs API key headers)
    if "coinbase.com/x402" in target.facilitator_base or target.name == "coinbase" or "coinbase" in target.name:
        try:
            from cdp.x402 import create_facilitator_config

            return create_facilitator_config(
                api_key_id=config.CDP_API_KEY_ID,
                api_key_secret=config.CDP_API_KEY_SECRET,
            )
        except Exception as exc:
            raise SystemExit(
                "Coinbase target requires cdp.x402 and CDP_API_KEY_ID/CDP_API_KEY_SECRET in config.py"
            ) from exc
    # Thirdweb facilitator uses x-secret-key header
    if "thirdweb" in target.name:
        try:
            secret = config.ThirdWeb_Secret_key
        except Exception as exc:
            raise SystemExit("Thirdweb target requires ThirdWeb_Secret_key in config.py") from exc

        async def _headers():
            return {
                "verify": {"x-secret-key": secret},
                "settle": {"x-secret-key": secret},
                "supported": {"x-secret-key": secret},
            }

        return FacilitatorConfig(url=target.facilitator_base, create_headers=_headers)

    return FacilitatorConfig(url=target.facilitator_base)


target = current_target(_resolve_target_name_from_cli())
NEEDPAY_PATH = target.needpay_path if target.needpay_path.startswith("/") else f"/{target.needpay_path}"

facilitator_config = _build_facilitator_config(target)

app = Flask(__name__)

# Initialize payment middleware
# This middleware will intercept requests and enforce payment for configured routes
payment_middleware = PaymentMiddleware(app)

# Apply payment middleware to specific routes
payment_middleware.add(
    path=NEEDPAY_PATH,
    price=target.price,
    pay_to_address=target.pay_to_address,
    network=target.network,
    facilitator_config=facilitator_config,
)

# Protected endpoint: clients must provide a valid x402 payment header to access this
@app.get(NEEDPAY_PATH)
def view_needpay():
    # If payment is valid and settled, this content will be returned
    return "paid content"

def run(target_name=None):
    import os
    if target_name:
        os.environ["TARGET"] = target_name

    app.run(host='0.0.0.0', port=8001, debug=True)

def main():
    run()


if __name__ == "__main__":
    main()
