# api/email_service.py
"""
Send meeting minutes by email.

Two providers are supported:
  - "smtp": any SMTP server (e.g. Gmail with an app password, Outlook, SendGrid SMTP)
  - "composio": Composio's GMAIL_SEND_EMAIL tool through a Gmail account
    connected in the Composio dashboard (called over Composio's v3.1 REST API;
    the legacy composio-core SDK endpoints now return HTTP 410)

EMAIL_PROVIDER picks one explicitly; otherwise SMTP is used when SMTP_HOST
is set, then Composio when COMPOSIO_API_KEY is set.
"""
import logging
import re
import smtplib
from email.message import EmailMessage

import requests

from app.export import minutes_to_html, minutes_to_markdown
from utils.config import get_email_settings

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

COMPOSIO_EXECUTE_URL = "https://backend.composio.dev/api/v3.1/tools/execute/GMAIL_SEND_EMAIL"


def active_provider(settings=None):
    """
    Returns:
        str|None: "smtp", "composio" or None when email is not configured
    """
    settings = settings or get_email_settings()
    smtp_ready = bool(settings["smtp_host"] and settings["email_from"])
    composio_ready = bool(settings["composio_api_key"])
    if settings["provider"] == "smtp":
        return "smtp" if smtp_ready else None
    if settings["provider"] == "composio":
        return "composio" if composio_ready else None
    if smtp_ready:
        return "smtp"
    if composio_ready:
        return "composio"
    return None


def parse_recipients(raw):
    """
    Split a comma/newline separated list of addresses

    Returns:
        tuple: (valid addresses, invalid entries)
    """
    entries = [part.strip() for part in re.split(r"[,;\n]", raw or "") if part.strip()]
    valid = list(dict.fromkeys(e for e in entries if _EMAIL_RE.match(e)))
    invalid = [e for e in entries if not _EMAIL_RE.match(e)]
    return valid, invalid


def send_minutes_email(meeting, recipients):
    """
    Email the minutes to each recipient

    Args:
        meeting: Meeting dict (title, meeting_date, minutes, ...)
        recipients: List of email addresses

    Returns:
        list: [{"recipient", "ok", "error"}] — one entry per recipient
    """
    settings = get_email_settings()
    provider = active_provider(settings)
    if provider is None:
        return [{"recipient": r, "ok": False, "error": "Email is not configured"} for r in recipients]

    subject = f"Meeting minutes: {meeting.get('title', 'Untitled meeting')}"
    html_body = minutes_to_html(meeting)
    text_body = minutes_to_markdown(meeting)

    if provider == "smtp":
        return _send_smtp(settings, recipients, subject, html_body, text_body)
    return _send_composio(settings, recipients, subject, html_body)


def _send_smtp(settings, recipients, subject, html_body, text_body):
    results = []
    try:
        if settings["smtp_port"] == 465:
            server = smtplib.SMTP_SSL(settings["smtp_host"], settings["smtp_port"], timeout=30)
        else:
            server = smtplib.SMTP(settings["smtp_host"], settings["smtp_port"], timeout=30)
            server.starttls()
        if settings["smtp_user"]:
            server.login(settings["smtp_user"], settings["smtp_password"] or "")
    except (smtplib.SMTPException, OSError) as e:
        logger.exception("SMTP connection failed")
        return [{"recipient": r, "ok": False, "error": f"Could not connect to the mail server: {e}"} for r in recipients]

    try:
        for recipient in recipients:
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = settings["email_from"]
            message["To"] = recipient
            message.set_content(text_body)
            message.add_alternative(html_body, subtype="html")
            try:
                server.send_message(message)
                results.append({"recipient": recipient, "ok": True, "error": None})
            except smtplib.SMTPException as e:
                results.append({"recipient": recipient, "ok": False, "error": str(e)})
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass
    return results


def _send_composio(settings, recipients, subject, html_body):
    """Send through Composio's GMAIL_SEND_EMAIL tool, one request per recipient"""
    headers = {"x-api-key": settings["composio_api_key"], "Content-Type": "application/json"}
    results = []
    for recipient in recipients:
        payload = {
            "user_id": settings["composio_user_id"],
            "arguments": {"recipient_email": recipient, "subject": subject, "body": html_body, "is_html": True},
        }
        if settings["composio_connected_account_id"]:
            payload["connected_account_id"] = settings["composio_connected_account_id"]
        try:
            response = requests.post(COMPOSIO_EXECUTE_URL, json=payload, headers=headers, timeout=60)
            data = response.json() if response.content else {}
        except (requests.RequestException, ValueError) as e:
            logger.exception("Composio send failed")
            results.append({"recipient": recipient, "ok": False, "error": f"Could not reach Composio: {e}"})
            continue
        ok = response.ok and bool(data.get("successful"))
        error = None if ok else (data.get("error") or (data.get("error_message")) or f"HTTP {response.status_code}")
        if isinstance(error, dict):
            error = error.get("message") or str(error)
        results.append({"recipient": recipient, "ok": ok, "error": _explain_composio_error(error)})
    return results


def _explain_composio_error(error):
    """Add the fix to Composio's errors for a missing or expired Gmail connection"""
    text = str(error or "")
    if "EXPIRED" in text or "No connected account" in text:
        return (
            f"{text}. Gmail needs to be (re)connected in Composio: open platform.composio.dev, go to "
            "Connected accounts, and connect Gmail again. If it isn't under the user ID 'default', "
            "set COMPOSIO_USER_ID in .env to the user ID shown there. If Google blocks the connection, "
            "send over SMTP instead with a Gmail app password (SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env)."
        )
    return error
