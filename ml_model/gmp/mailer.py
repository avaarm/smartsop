"""Minimal SMTP email sender, configured by environment variables.

Enabled only when SMTP_HOST is set — otherwise send_email() is a no-op that
returns False, so features that use it (e.g. password reset) degrade gracefully
on a self-hosted instance that hasn't configured mail yet.

Env:
  SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD,
  SMTP_FROM (default: SMTP_USER), SMTP_TLS (default "true" → STARTTLS).
"""

import os
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True on success, False if not configured
    or on failure (logged). Never raises."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM") or user or "no-reply@smartsop.local"
    use_tls = os.environ.get("SMTP_TLS", "true").lower() in ("1", "true", "yes")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        logger.info("Sent email to %s (subject=%r)", to_address, subject)
        return True
    except Exception as e:  # noqa: BLE001 — never break the request on mail failure
        logger.warning("Failed to send email to %s: %s", to_address, e)
        return False
