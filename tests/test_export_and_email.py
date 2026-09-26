import io
import smtplib

from docx import Document

from api import email_service
from app.export import minutes_to_docx, minutes_to_html, minutes_to_markdown


def test_markdown_contains_minutes_sections(sample_meeting):
    md = minutes_to_markdown(sample_meeting)
    assert md.startswith("# Meeting minutes: Q3 budget review")
    assert "**Duration:** 30 min" in md
    assert "- Priya (Chair)" in md
    assert "- Freeze hiring until Q4 (Priya)" in md
    assert "| Send revised budget | Ravi | 2026-09-30 | High | Open |" in md
    assert "| Update hiring plan \\| pipeline | Unassigned | No date | Medium | Done |" in md


def test_html_escapes_content(sample_meeting):
    html = minutes_to_html(sample_meeting)
    assert "&lt;freeze&gt;" in html and "<freeze>" not in html
    assert "&amp; agreed" in html


def test_docx_has_action_item_table(sample_meeting):
    doc = Document(io.BytesIO(minutes_to_docx(sample_meeting)))
    rows = [[cell.text for cell in row.cells] for row in doc.tables[0].rows]
    assert rows[0] == ["Task", "Owner", "Due", "Priority", "Status"]
    assert rows[1] == ["Send revised budget", "Ravi", "2026-09-30", "High", "Open"]


def test_empty_minutes_render_without_errors():
    meeting = {"title": "Empty", "minutes": {}}
    assert "No decisions were recorded." in minutes_to_markdown(meeting)
    assert "No action items were recorded." in minutes_to_html(meeting)
    assert minutes_to_docx(meeting)


def test_parse_recipients():
    valid, invalid = email_service.parse_recipients("a@x.com, b@y.org\nnot-an-email; a@x.com")
    assert valid == ["a@x.com", "b@y.org"]
    assert invalid == ["not-an-email"]


def test_provider_selection(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("COMPOSIO_API_KEY", "")
    assert email_service.active_provider() is None
    monkeypatch.setenv("COMPOSIO_API_KEY", "ck")
    assert email_service.active_provider() == "composio"
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_FROM", "bot@example.com")
    assert email_service.active_provider() == "smtp"
    monkeypatch.setenv("EMAIL_PROVIDER", "composio")
    assert email_service.active_provider() == "composio"


def test_unconfigured_email_reports_failure_for_everyone(sample_meeting):
    results = email_service.send_minutes_email(sample_meeting, ["a@x.com"])
    assert results == [{"recipient": "a@x.com", "ok": False, "error": "Email is not configured"}]


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host = host

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        if message["To"] == "bounce@x.com":
            raise smtplib.SMTPRecipientsRefused({message["To"]: (550, b"no such user")})
        FakeSMTP.sent.append(message)

    def quit(self):
        pass


def test_smtp_reports_per_recipient_results(monkeypatch, sample_meeting):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "bot@example.com")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []

    results = email_service.send_minutes_email(sample_meeting, ["a@x.com", "bounce@x.com"])

    assert [r["ok"] for r in results] == [True, False]
    message = FakeSMTP.sent[0]
    assert message["Subject"] == "Meeting minutes: Q3 budget review"
    assert message["From"] == "bot@example.com"
    html = message.get_body(("html",)).get_content()
    assert "Send revised budget" in html and "&lt;freeze&gt;" in html


def test_composio_uses_the_v3_rest_api(monkeypatch, sample_meeting):
    monkeypatch.setenv("COMPOSIO_API_KEY", "ck-test")
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    calls = []

    class Response:
        def __init__(self, status, body):
            self.status_code, self._body, self.ok, self.content = status, body, status < 400, b"x"

        def json(self):
            return self._body

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        if json["arguments"]["recipient_email"] == "bad@x.com":
            return Response(200, {"successful": False, "error": "Recipient address rejected", "data": {}})
        return Response(200, {"successful": True, "error": None, "data": {"id": "msg1"}})

    monkeypatch.setattr(email_service.requests, "post", fake_post)
    results = email_service.send_minutes_email(sample_meeting, ["a@x.com", "bad@x.com"])

    assert [(r["ok"], r["error"]) for r in results] == [(True, None), (False, "Recipient address rejected")]
    first = calls[0]
    assert first["url"] == "https://backend.composio.dev/api/v3.1/tools/execute/GMAIL_SEND_EMAIL"
    assert first["headers"]["x-api-key"] == "ck-test"
    assert first["json"]["user_id"] == "default" and "connected_account_id" not in first["json"]
    arguments = first["json"]["arguments"]
    assert arguments["recipient_email"] == "a@x.com" and arguments["is_html"] is True
    assert arguments["subject"] == "Meeting minutes: Q3 budget review" and "&lt;freeze&gt;" in arguments["body"]


def test_expired_composio_gmail_connection_explains_the_fix(monkeypatch, sample_meeting):
    monkeypatch.setenv("COMPOSIO_API_KEY", "ck-test")

    class Response:
        status_code, ok, content = 400, False, b"x"

        def json(self):
            return {"successful": False, "error": {"message": "Connected account abc for toolkit 'gmail' is in EXPIRED state"}}

    monkeypatch.setattr(email_service.requests, "post", lambda *args, **kwargs: Response())
    [result] = email_service.send_minutes_email(sample_meeting, ["a@x.com"])

    assert result["ok"] is False
    assert result["error"].startswith("Connected account abc for toolkit 'gmail' is in EXPIRED state.")
    assert "platform.composio.dev" in result["error"] and "COMPOSIO_USER_ID" in result["error"] and "SMTP" in result["error"]


def test_smtp_connection_failure_is_reported(monkeypatch, sample_meeting):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_FROM", "bot@example.com")

    def refuse(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", refuse)
    results = email_service.send_minutes_email(sample_meeting, ["a@x.com"])
    assert not results[0]["ok"] and "connection refused" in results[0]["error"]
