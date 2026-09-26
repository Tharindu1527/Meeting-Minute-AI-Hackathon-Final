# server/auth.py
"""
Optional shared-password sign-in (enabled by setting APP_PASSWORD).

Signing in returns a token: an expiry time signed with a key derived from the
password, so no session storage is needed and changing the password signs
everyone out.
"""
import hashlib
import hmac
import time
from typing import Optional

from fastapi import Header, HTTPException

from utils.config import get_app_password

TOKEN_LIFETIME_SECONDS = 7 * 24 * 3600


def _signature(password, expires):
    key = hashlib.sha256(f"meeting-minutes:{password}".encode()).digest()
    return hmac.new(key, expires.encode(), hashlib.sha256).hexdigest()


def issue_token(password):
    expires = str(int(time.time()) + TOKEN_LIFETIME_SECONDS)
    return f"{expires}.{_signature(password, expires)}"


def token_is_valid(token, password):
    expires, _, signature = (token or "").partition(".")
    if not expires.isdigit() or not signature:
        return False
    return hmac.compare_digest(signature, _signature(password, expires)) and int(expires) > time.time()


def password_matches(candidate):
    password = get_app_password()
    return bool(password) and hmac.compare_digest((candidate or "").encode(), password.encode())


def require_auth(authorization: Optional[str] = Header(default=None)):
    """FastAPI dependency: reject requests without a valid token when APP_PASSWORD is set"""
    password = get_app_password()
    if not password:
        return
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token_is_valid(token, password):
        raise HTTPException(status_code=401, detail="Please sign in.")
