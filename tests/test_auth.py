"""Accounts: sign-up rules, sign-in, sessions, password change/reset and account deletion"""
import json
import time

import pytest
from fastapi.testclient import TestClient

import server.main
import server.routes.auth as auth_routes
import server.routes.status
from server import auth

PASSWORD = "correct horse battery"


@pytest.fixture
def anon(mongo):
    server.routes.status._db_status.update(checked_at=time.time(), ok=True, error=None)
    return TestClient(server.main.create_app())


def register(client, email="ana@example.com", password=PASSWORD, name="Ana", **extra):
    return client.post("/api/auth/register", json=dict(name=name, email=email, password=password, **extra))


def bearer(session):
    return {"Authorization": f"Bearer {session['token']}"}


@pytest.fixture
def outbox(monkeypatch):
    """Email 'configured', with sent messages captured instead of delivered"""
    sent = []
    monkeypatch.setenv("COMPOSIO_API_KEY", "ck")
    monkeypatch.setattr(auth_routes, "send_email", lambda recipients, subject, html, text: sent.append(
        {"to": recipients, "subject": subject, "text": text}) or [{"recipient": recipients[0], "ok": True, "error": None}])
    return sent


def test_passwords_are_salted_and_verified():
    first, second = auth.hash_password("pa55word!"), auth.hash_password("pa55word!")
    assert first != second and first.startswith("scrypt$") and "pa55word" not in first
    assert auth.verify_password("pa55word!", first) and not auth.verify_password("pa55word?", first)
    assert not auth.verify_password("anything", None) and not auth.verify_password("x", "garbage")


def test_register_sign_in_and_profile(anon):
    session = register(anon, email="  Ana@Example.com ", name="  Ana   Silva ").json()
    assert session["user"]["email"] == "ana@example.com" and session["user"]["name"] == "Ana Silva"
    assert "password_hash" not in session["user"] and session["expires_at"] > time.time() + 29 * 24 * 3600

    assert anon.get("/api/auth/me", headers=bearer(session)).json()["email"] == "ana@example.com"
    assert anon.post("/api/auth/login", json={"email": "ana@example.com", "password": "wrong"}).status_code == 401
    assert anon.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}).status_code == 401
    short = anon.post("/api/auth/login", json={"email": "ANA@example.com", "password": PASSWORD, "remember": False}).json()
    assert short["expires_at"] < time.time() + 13 * 3600

    renamed = anon.patch("/api/auth/me", json={"name": "Ana S."}, headers=bearer(short)).json()
    assert renamed["name"] == "Ana S."
    assert anon.patch("/api/auth/me", json={"name": "   "}, headers=bearer(short)).status_code == 400


@pytest.mark.parametrize("overrides, status, message", [
    ({"email": "not-an-email"}, 400, "valid email"),
    ({"name": " "}, 400, "your name"),
    ({"password": "short"}, 400, "at least 8"),
    ({"password": "password123"}, 400, "too easy"),
    ({"password": "aaaaaaaaaa"}, 400, "too easy"),
    ({"email": "ana.silva@example.com", "password": "ana.silva"}, 400, "email name"),
])
def test_register_rejects_bad_details(anon, overrides, status, message):
    response = register(anon, **overrides)
    assert response.status_code == status and message in response.json()["detail"]


def test_one_account_per_email(anon):
    assert register(anon).status_code == 201
    duplicate = register(anon, email="ANA@example.com")
    assert duplicate.status_code == 409 and "already exists" in duplicate.json()["detail"]


def test_first_account_gets_meetings_saved_before_accounts(anon, mongo, sample_meeting):
    legacy = str(mongo.get_collection().insert_one(dict(sample_meeting)).inserted_id)
    first = register(anon).json()
    second = register(anon, email="ben@example.com").json()
    assert [m["id"] for m in anon.get("/api/meetings", headers=bearer(first)).json()] == [legacy]
    assert anon.get("/api/meetings", headers=bearer(second)).json() == []


def test_closed_sign_up_still_allows_the_first_account(anon, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "false")
    assert anon.get("/api/status").json()["auth"]["signup_open"] is True
    assert register(anon).status_code == 201
    assert anon.get("/api/status").json()["auth"]["signup_open"] is False
    closed = register(anon, email="ben@example.com")
    assert closed.status_code == 403 and "closed" in closed.json()["detail"]


def test_invite_code(anon, monkeypatch):
    monkeypatch.setenv("SIGNUP_CODE", "team-2026")
    assert anon.get("/api/status").json()["auth"]["invite_code_required"] is True
    assert register(anon).status_code == 201  # the first account sets the app up without one
    assert register(anon, email="ben@example.com", invite_code="guess").status_code == 403
    assert register(anon, email="ben@example.com", invite_code=" team-2026 ").status_code == 201


def test_repeated_failed_sign_ins_are_blocked(anon):
    register(anon)
    for _ in range(8):
        assert anon.post("/api/auth/login", json={"email": "ana@example.com", "password": "nope"}).status_code == 401
    blocked = anon.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    assert blocked.status_code == 429 and "Too many attempts" in blocked.json()["detail"]


def test_changing_the_password_signs_out_other_sessions(anon):
    laptop = register(anon).json()
    phone = anon.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD}).json()

    wrong = anon.post("/api/auth/change-password", headers=bearer(laptop),
                      json={"current_password": "nope", "new_password": "new strong pass 42"})
    assert wrong.status_code == 400 and "current password" in wrong.json()["detail"]
    fresh = anon.post("/api/auth/change-password", headers=bearer(laptop),
                      json={"current_password": PASSWORD, "new_password": "new strong pass 42"}).json()

    assert anon.get("/api/auth/me", headers=bearer(phone)).status_code == 401
    assert anon.get("/api/auth/me", headers=bearer(laptop)).status_code == 401
    assert anon.get("/api/auth/me", headers=bearer(fresh)).status_code == 200
    assert anon.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD}).status_code == 401
    assert anon.post("/api/auth/login", json={"email": "ana@example.com", "password": "new strong pass 42"}).status_code == 200


def test_sign_out_other_devices(anon):
    laptop = register(anon).json()
    phone = anon.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD}).json()
    fresh = anon.post("/api/auth/sign-out-others", headers=bearer(laptop), json={}).json()
    assert anon.get("/api/auth/me", headers=bearer(phone)).status_code == 401
    assert anon.get("/api/auth/me", headers=bearer(fresh)).status_code == 200


def test_forged_expired_and_wrong_purpose_tokens_are_rejected(anon):
    session = register(anon).json()
    header, body, signature = session["token"].split(".")
    user_id = session["user"]["id"]

    def b64json(value):
        return auth._b64(json.dumps(value).encode())

    tampered = f"{header}.{b64json({'purpose': 'session', 'sub': 'x', 'ver': 0, 'exp': 9999999999})}.{signature}"
    expired = auth.encode_token({"purpose": "session", "sub": user_id, "ver": 0, "exp": int(time.time()) - 1})
    reset = auth.encode_token({"purpose": "reset", "sub": user_id, "ver": 0, "exp": int(time.time()) + 60})
    unsigned = f"{b64json({'alg': 'none', 'typ': 'JWT'})}.{body}."
    for token in (tampered, expired, reset, unsigned, "garbage"):
        assert anon.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_password_reset_by_email(anon, outbox):
    old_session = register(anon).json()
    assert anon.get("/api/status").json()["auth"]["password_reset"] is True

    assert anon.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).json() == {"sent": True}
    assert outbox == []  # same answer, but nothing is sent for unknown addresses
    assert anon.post("/api/auth/forgot-password", json={"email": "Ana@example.com"}).json() == {"sent": True}
    assert outbox[0]["to"] == ["ana@example.com"]
    token = outbox[0]["text"].split("#token=")[1].split()[0]
    assert "http://testserver/reset-password#token=" in outbox[0]["text"]

    assert anon.post("/api/auth/reset-password/check", json={"token": token}).json() == {"email": "ana@example.com"}
    assert anon.post("/api/auth/reset-password", json={"token": token, "password": "short"}).status_code == 400
    session = anon.post("/api/auth/reset-password", json={"token": token, "password": "brand new secret 7"}).json()

    assert anon.get("/api/auth/me", headers=bearer(session)).status_code == 200
    assert anon.get("/api/auth/me", headers=bearer(old_session)).status_code == 401
    reused = anon.post("/api/auth/reset-password", json={"token": token, "password": "another secret 99"})
    assert reused.status_code == 400 and "already used" in reused.json()["detail"]
    assert anon.post("/api/auth/login", json={"email": "ana@example.com", "password": "brand new secret 7"}).status_code == 200


def test_reset_links_use_app_url_when_set(anon, outbox, monkeypatch):
    monkeypatch.setenv("APP_URL", "https://minutes.example.com/")
    register(anon)
    anon.post("/api/auth/forgot-password", json={"email": "ana@example.com"})
    assert "https://minutes.example.com/reset-password#token=" in outbox[0]["text"]


def test_password_reset_needs_email_configured(anon):
    register(anon)
    response = anon.post("/api/auth/forgot-password", json={"email": "ana@example.com"})
    assert response.status_code == 400 and "isn't set up" in response.json()["detail"]


def test_delete_account_removes_its_meetings(anon, mongo, sample_meeting):
    session = register(anon).json()
    mongo.create_meeting(sample_meeting, session["user"]["id"])

    assert anon.post("/api/auth/delete-account", headers=bearer(session), json={"password": "nope"}).status_code == 400
    deleted = anon.post("/api/auth/delete-account", headers=bearer(session), json={"password": PASSWORD}).json()
    assert deleted == {"deleted": True, "meetings_deleted": 1}
    assert mongo.list_meetings(session["user"]["id"]) == []
    assert anon.get("/api/auth/me", headers=bearer(session)).status_code == 401
    assert anon.post("/api/auth/login", json={"email": "ana@example.com", "password": PASSWORD}).status_code == 401
