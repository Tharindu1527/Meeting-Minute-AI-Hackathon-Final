"""
Copy the settings from .env into a Hugging Face Space as secrets.

Run it yourself after logging in with `hf auth login`:

    venv\\Scripts\\python scripts\\hf_space_secrets.py <username>/<space-name>

Values go straight from your .env to Hugging Face and are never printed.
The Space restarts automatically to pick them up.
"""
import os
import sys

from dotenv import dotenv_values
from huggingface_hub import HfApi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        print(__doc__)
        sys.exit(1)
    space = sys.argv[1]
    values = {key: value for key, value in dotenv_values(os.path.join(ROOT, ".env")).items() if value}
    if not values.get("SIGNUP_CODE") and values.get("ALLOW_SIGNUP", "true").lower() not in ("0", "false", "no", "off"):
        print("Warning: SIGNUP_CODE is empty and sign-up is open, so anyone who opens the Space can create an account "
              "and use your Gemini quota. Set SIGNUP_CODE, or ALLOW_SIGNUP=false once your account exists.")
    values.pop("APP_PASSWORD", None)  # replaced by accounts
    local_qdrant = values.get("QDRANT_URI", "").startswith((".", "/")) or values.get("QDRANT_URI") == ":memory:"
    if local_qdrant:
        print("Skipping QDRANT_URI: a local folder does not survive Space restarts (chat falls back to keyword search).")
        values.pop("QDRANT_URI")

    api = HfApi()
    # Password-reset emails must link to the Space, not to a local address from .env
    if not values.get("APP_URL") or "localhost" in values["APP_URL"] or "127.0.0.1" in values["APP_URL"]:
        host = api.space_info(space).host
        if host:
            values["APP_URL"] = host
            print("APP_URL will be", host)
    for key, value in values.items():
        api.add_space_secret(space, key, value)
        print("set", key)
    print(f"Done: {len(values)} secrets added to {space}.")


if __name__ == "__main__":
    main()
