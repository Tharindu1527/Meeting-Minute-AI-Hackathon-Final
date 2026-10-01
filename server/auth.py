# server/auth.py
"""
User accounts: password hashing, sign-in tokens and the current-user check.

- Passwords are hashed with scrypt (Python standard library) and a random salt.
- Sign-in tokens are JWTs (HS256) holding the user id and the account's
  token version. Changing or resetting the password bumps the version, which
  signs out every other session. Password-reset tokens are JWTs too, tied to
  the current password hash so each one works only once.
- The signing key is AUTH_SECRET, or a random key generated once and kept in
  MongoDB so sessions survive restarts.
- Failed sign-ins and reset requests are rate-limited in memory.
"""
import base64
import binascii
import hashlib
import hmac
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Request

from database import users
from utils.config import get_auth_secret

SESSION_SECONDS = 30 * 24 * 3600       # "Keep me signed in"
SHORT_SESSION_SECONDS = 12 * 3600      # otherwise (the browser also forgets it when closed)
RESET_SECONDS = 3600
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# scrypt cost: ~50 ms per hash, 16 MB of memory
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
_COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890", "qwerty123", "qwertyuiop",
    "iloveyou", "11111111", "00000000", "abc12345", "letmein1", "welcome1", "admin123", "passw0rd", "sunshine",
    "football", "baseball", "princess", "trustno1", "meeting123",
}

_secret_key = None
_secret_lock = threading.Lock()


# --- Passwords -----------------------------------------------------------------------------------

def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=64, **_SCRYPT)
    return "scrypt${n}${r}${p}${salt}${hash}".format(
        salt=base64.b64encode(salt).decode(), hash=base64.b64encode(digest).decode(), **_SCRYPT)


def verify_password(password, stored):
    """Check a password against a stored hash; also spends the same time when there is no account"""
    if not stored:
        hash_password(password or "")  # equal timing, so response times don't reveal which emails have accounts
        return False
    try:
        _, n, r, p, salt, expected = stored.split("$")
        digest = hashlib.scrypt((password or "").encode(), salt=base64.b64decode(salt), dklen=64,
                                n=int(n), r=int(r), p=int(p))
    except (ValueError, binascii.Error):
        return False
    return hmac.compare_digest(digest, base64.b64decode(expected))


def password_problem(password, email=""):
    """Why a new password isn't acceptable, or None when it's fine"""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters for your password."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Use at most {MAX_PASSWORD_LENGTH} characters for your password."
    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS or len(set(password)) < 4:
        return "That password is too easy to guess. Try a few unrelated words or add numbers and symbols."
    if email and lowered == email.split("@")[0].lower():
        return "Your password can't be the same as your email name."
    return None


# --- Tokens ---------------------------------------------------------------------------------------

def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


_JWT_HEADER = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())


def _secret():
    global _secret_key
    if _secret_key is None:
        with _secret_lock:
            if _secret_key is None:
                configured = get_auth_secret()
                _secret_key = configured.encode() if configured else users.load_or_create_secret()
    return _secret_key


def _sign(signing_input):
    return hmac.new(_secret(), signing_input.encode(), hashlib.sha256).digest()


def encode_token(claims):
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{_JWT_HEADER}.{body}.{_b64(_sign(f'{_JWT_HEADER}.{body}'))}"


def decode_token(token, purpose):
    """The token's claims when it is genuine, unexpired and issued for `purpose`; otherwise None"""
    parts = (token or "").split(".")
    # Only our own header is accepted, so a token can't pick a weaker algorithm
    if len(parts) != 3 or parts[0] != _JWT_HEADER:
        return None
    try:
        if not hmac.compare_digest(_unb64(parts[2]), _sign(f"{parts[0]}.{parts[1]}")):
            return None
        claims = json.loads(_unb64(parts[1]))
    except (ValueError, binascii.Error):
        return None
    if not isinstance(claims, dict) or claims.get("purpose") != purpose or not isinstance(claims.get("exp"), int):
        return None
    return claims if claims["exp"] > time.time() else None


def issue_session(user, remember=True):
    """
    Sign-in response for a user

    Returns:
        dict: {"token", "expires_at" (unix seconds), "user"}
    """
    now = int(time.time())
    expires = now + (SESSION_SECONDS if remember else SHORT_SESSION_SECONDS)
    token = encode_token({"purpose": "session", "sub": str(user["_id"]), "ver": user.get("token_version", 0),
                          "iat": now, "exp": expires})
    return {"token": token, "expires_at": expires, "user": users.public_user(user)}


def _password_fingerprint(user):
    return hashlib.sha256(user["password_hash"].encode()).hexdigest()[:16]


def issue_reset_token(user):
    return encode_token({"purpose": "reset", "sub": str(user["_id"]), "pwd": _password_fingerprint(user),
                         "exp": int(time.time()) + RESET_SECONDS})


def user_from_reset_token(token):
    """The account a reset token belongs to, or None when it is invalid, expired or already used"""
    claims = decode_token(token, "reset")
    user = users.get_user(claims["sub"]) if claims else None
    if user is None or not hmac.compare_digest(claims.get("pwd", ""), _password_fingerprint(user)):
        return None
    return user


def current_user(authorization: Optional[str] = Header(default=None)):
    """FastAPI dependency: the signed-in user's account, or 401"""
    token = (authorization or "").removeprefix("Bearer ").strip()
    claims = decode_token(token, "session") if token else None
    if not claims:
        raise HTTPException(status_code=401, detail="Please sign in.")
    user = users.get_user(claims.get("sub"))
    if user is None or user.get("token_version", 0) != claims.get("ver"):
        raise HTTPException(status_code=401, detail="Your session has ended. Please sign in again.")
    return user


CurrentUser = Annotated[dict, Depends(current_user)]


def user_id(user):
    return str(user["_id"])


# --- Rate limiting ---------------------------------------------------------------------------------

class RateLimiter:
    """At most `limit` events per key in a sliding window of `window` seconds (in memory, per process)"""

    def __init__(self, limit, window):
        self.limit, self.window = limit, window
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key):
        """The key's events inside the window; keys with none left are dropped so memory stays bounded"""
        events, cutoff = self._events.get(key), time.time() - self.window
        while events and events[0] < cutoff:
            events.popleft()
        if not events:
            self._events.pop(key, None)
            return deque()
        return events

    def check(self, key):
        """Raise 429 when the key has used up its attempts"""
        with self._lock:
            events = self._recent(key)
            if len(events) >= self.limit:
                minutes = max(1, round((events[0] + self.window - time.time()) / 60))
                raise HTTPException(status_code=429, detail=f"Too many attempts. Please try again in {minutes} "
                                                            f"minute{'s' if minutes != 1 else ''}.")

    def hit(self, key):
        with self._lock:
            self._recent(key)
            self._events[key].append(time.time())

    def reset(self, key=None):
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)


failed_logins = RateLimiter(limit=8, window=15 * 60)
account_requests = RateLimiter(limit=10, window=60 * 60)  # sign-ups and password-reset emails per address


def client_ip(request: Request):
    """The caller's address (the first X-Forwarded-For hop behind a proxy such as Hugging Face Spaces)"""
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
