# server/routes/auth.py
"""Accounts: sign up, sign in, profile, password change and reset, sign out elsewhere, delete account"""
import hmac
import html
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from api.email_service import active_provider, is_valid_email, send_email
from database import mongodb, qdrant, users
from server.auth import (
    CurrentUser,
    account_requests,
    client_ip,
    failed_logins,
    hash_password,
    issue_reset_token,
    issue_session,
    password_problem,
    user_from_reset_token,
    user_id,
    verify_password,
)
from utils.config import get_app_url, get_signup_code, is_signup_allowed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _email(raw):
    """Normalised email address, or 400 when it isn't one"""
    email = (raw or "").strip().lower()
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return email


def _check_new_password(password, email):
    problem = password_problem(password, email)
    if problem:
        raise HTTPException(status_code=400, detail=problem)


def _check_current_password(user, password):
    """Confirm the signed-in user's password before a sensitive change (rate-limited like sign-in)"""
    key = f"account|{user_id(user)}"
    failed_logins.check(key)
    if not verify_password(password, user.get("password_hash")):
        failed_logins.hit(key)
        raise HTTPException(status_code=400, detail="Your current password isn't right.")
    failed_logins.reset(key)


def signup_open():
    """Whether a new account can be created right now (the first account always can)"""
    return is_signup_allowed() or users.count_users() == 0


class RegisterRequest(BaseModel):
    name: str = Field(max_length=80)
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    invite_code: str = Field(default="", max_length=200)
    remember: bool = True


@router.post("/register", status_code=201)
def register(body: RegisterRequest, request: Request):
    ip_key = f"signup|{client_ip(request)}"
    account_requests.check(ip_key)
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status_code=400, detail="Enter your name.")
    email = _email(body.email)

    first_account = users.count_users() == 0
    if not first_account:
        if not is_signup_allowed():
            raise HTTPException(status_code=403, detail="Sign-up is closed. Ask the app's owner to create an account for you.")
        code = get_signup_code()
        if code and not hmac.compare_digest(body.invite_code.strip().encode(), code.encode()):
            account_requests.hit(ip_key)
            raise HTTPException(status_code=403, detail="That invite code isn't right.")
    _check_new_password(body.password, email)

    account_requests.hit(ip_key)
    try:
        user = users.create_user(email, name, hash_password(body.password))
    except users.EmailTaken:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.")
    if first_account:
        # Meetings saved before accounts existed belong to whoever set the app up
        claimed = mongodb.claim_unowned_meetings(user_id(user))
        if claimed:
            logger.info("Gave %d earlier meetings to the first account", claimed)
    return issue_session(user, body.remember)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    remember: bool = True


@router.post("/login")
def login(body: LoginRequest, request: Request):
    email = body.email.strip().lower()
    key = f"{client_ip(request)}|{email}"
    failed_logins.check(key)
    user = users.find_user_by_email(email) if email else None
    if not verify_password(body.password, user.get("password_hash") if user else None):
        failed_logins.hit(key)
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    failed_logins.reset(key)
    users.record_login(user_id(user))
    return issue_session(user, body.remember)


@router.get("/me")
def me(user: CurrentUser):
    return users.public_user(user)


class ProfileUpdate(BaseModel):
    name: str = Field(max_length=80)


@router.patch("/me")
def update_profile(body: ProfileUpdate, user: CurrentUser):
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status_code=400, detail="Enter your name.")
    return users.public_user(users.update_user(user_id(user), {"name": name}))


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)
    remember: bool = True


@router.post("/change-password")
def change_password(body: PasswordChange, user: CurrentUser):
    """Set a new password; other devices are signed out and this one gets a fresh session"""
    _check_current_password(user, body.current_password)
    _check_new_password(body.new_password, user["email"])
    updated = users.end_sessions(user_id(user), hash_password(body.new_password))
    return issue_session(updated, body.remember)


class SessionRequest(BaseModel):
    remember: bool = True


@router.post("/sign-out-others")
def sign_out_others(body: SessionRequest, user: CurrentUser):
    """End every other session; this device gets a fresh one"""
    return issue_session(users.end_sessions(user_id(user)), body.remember)


class PasswordConfirmation(BaseModel):
    password: str = Field(max_length=256)


@router.post("/delete-account")
def delete_account(body: PasswordConfirmation, user: CurrentUser):
    """Delete the account and every meeting in it"""
    _check_current_password(user, body.password)
    meeting_ids = mongodb.delete_meetings_of(user_id(user))
    if qdrant.is_configured():
        for meeting_id in meeting_ids:
            try:
                qdrant.delete_meeting_vectors(meeting_id)
            except Exception:  # the meetings are gone either way; leftovers can't be searched without them
                logger.exception("Could not delete search vectors of meeting %s", meeting_id)
    users.delete_user(user_id(user))
    return {"deleted": True, "meetings_deleted": len(meeting_ids)}


# --- Forgotten passwords ----------------------------------------------------------------------------

def _app_url(request):
    """Base address for links in emails: APP_URL, or the address this request came in on"""
    configured = get_app_url()
    if configured:
        return configured
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    return f"{scheme}://{request.url.netloc}"


def _send_reset_email(user, link):
    name = html.escape(user.get("name") or "there")
    html_body = f"""<div style="font-family:Segoe UI,Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;color:#0f1222">
  <h2 style="margin:0 0 12px">Reset your password</h2>
  <p>Hi {name},</p>
  <p>Someone (hopefully you) asked to reset the password for your Meeting Minutes AI account.
     The link works once and expires in an hour.</p>
  <p style="margin:28px 0"><a href="{html.escape(link)}" style="background:#5b5bf6;color:#fff;padding:12px 22px;
     border-radius:10px;text-decoration:none;font-weight:600">Choose a new password</a></p>
  <p style="color:#5d647a;font-size:13px">If you didn't ask for this, ignore this email: your password stays the same.</p>
</div>"""
    text_body = (f"Hi {user.get('name') or 'there'},\n\nReset your Meeting Minutes AI password with this link "
                 f"(it works once and expires in an hour):\n{link}\n\nIf you didn't ask for this, ignore this email.")
    result = send_email([user["email"]], "Reset your Meeting Minutes AI password", html_body, text_body)[0]
    if not result["ok"]:
        logger.error("Could not send the password-reset email: %s", result["error"])


class ForgotRequest(BaseModel):
    email: str = Field(max_length=254)


@router.post("/forgot-password")
def forgot_password(body: ForgotRequest, request: Request, background: BackgroundTasks):
    """
    Email a reset link. The answer is the same whether or not the address has an
    account, and the email is sent after responding, so neither reveals who has one.
    """
    if active_provider() is None:
        raise HTTPException(status_code=400, detail="Password reset by email isn't set up on this server. "
                                                    "Ask the app's owner to help you sign in.")
    email = _email(body.email)
    for key in (f"reset|{client_ip(request)}", f"reset|{email}"):
        account_requests.check(key)
        account_requests.hit(key)
    user = users.find_user_by_email(email)
    if user:
        link = f"{_app_url(request)}/reset-password#token={issue_reset_token(user)}"
        background.add_task(_send_reset_email, user, link)
    return {"sent": True}


class ResetToken(BaseModel):
    token: str = Field(max_length=2000)


def _reset_user(token):
    user = user_from_reset_token(token)
    if user is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid, expired or already used. Request a new one.")
    return user


@router.post("/reset-password/check")
def check_reset_token(body: ResetToken):
    """Confirm a reset link before showing the form, and say which account it is for"""
    return {"email": _reset_user(body.token)["email"]}


class PasswordReset(ResetToken):
    password: str = Field(max_length=256)


@router.post("/reset-password")
def reset_password(body: PasswordReset):
    user = _reset_user(body.token)
    _check_new_password(body.password, user["email"])
    return issue_session(users.end_sessions(user_id(user), hash_password(body.password)), remember=True)
