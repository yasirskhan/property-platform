# ============================================================
# email.py
# ------------------------------------------------------------
# Sends emails. Three ways of choosing SMTP config:
#
#   1. If organization_id is passed AND that org has custom
#      email settings enabled -> use the org's SMTP.
#   2. Otherwise -> fall back to platform-level SMTP (config.py).
#   3. In "console" mode -> just print to the server log (dev).
#
# Usage:
#   send_email(to=..., subject=..., body=...)
#   send_email(to=..., subject=..., body=..., organization_id=5)
# ============================================================

import smtplib
from email.message import EmailMessage
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt


def send_email(
    to: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
    organization_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> None:
    """
    Send an email.

    If organization_id + db are provided and the org has custom SMTP,
    use those settings. Otherwise fall back to platform settings.
    """
    # Console dev mode
    if settings.EMAIL_MODE == "console":
        _send_console(to, subject, body, organization_id)
        return

    # Resolve SMTP config
    smtp_config = _resolve_smtp(organization_id, db)

    if smtp_config is None:
        raise RuntimeError("No SMTP configuration available")

    _send_smtp(to, subject, body, html, smtp_config)


# ------------------------------------------------------------
# SMTP config resolution
# ------------------------------------------------------------
def _resolve_smtp(organization_id: Optional[int], db: Optional[Session]):
    """
    Returns a dict with SMTP settings, or None.
    Prefers the org's settings; falls back to platform settings.
    """
    # Try org settings first
    if organization_id is not None and db is not None:
        from app.models.org_email import OrganizationEmailSettings
        org_settings = (
            db.query(OrganizationEmailSettings)
            .filter(
                OrganizationEmailSettings.organization_id == organization_id,
                OrganizationEmailSettings.is_enabled == True,  # noqa: E712
            )
            .first()
        )
        if org_settings:
            try:
                return {
                    "host": org_settings.smtp_host,
                    "port": org_settings.smtp_port,
                    "user": org_settings.smtp_user,
                    "password": decrypt(org_settings.smtp_password_encrypted),
                    "use_tls": org_settings.smtp_use_tls,
                    "from_email": org_settings.from_email,
                    "from_name": org_settings.from_name,
                    "reply_to": org_settings.reply_to_email,
                }
            except Exception as e:
                print(f"⚠️  Could not decrypt org SMTP password (org={organization_id}): {e}")

    # Fall back to platform settings
    if settings.SMTP_HOST and settings.SMTP_USER:
        return {
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "user": settings.SMTP_USER,
            "password": settings.SMTP_PASSWORD,
            "use_tls": settings.SMTP_USE_TLS,
            "from_email": settings.EMAIL_FROM,
            "from_name": settings.EMAIL_FROM_NAME,
            "reply_to": None,
        }

    return None


# ------------------------------------------------------------
# Console mode (dev)
# ------------------------------------------------------------
def _send_console(
    to: str, subject: str, body: str, organization_id: Optional[int]
):
    border = "=" * 70
    source = (
        f"custom SMTP (org={organization_id})"
        if organization_id
        else "platform default (dev console)"
    )
    print(f"\n{border}")
    print(f"📧 EMAIL (dev mode — {source})")
    print(f"To:      {to}")
    print(f"Subject: {subject}")
    print(f"{'-' * 70}")
    print(body)
    print(f"{border}\n")


# ------------------------------------------------------------
# Actual SMTP send
# ------------------------------------------------------------
def _send_smtp(
    to: str,
    subject: str,
    body: str,
    html: Optional[str],
    config: dict,
) -> None:
    msg = EmailMessage()

    from_name = config.get("from_name") or ""
    from_email = config["from_email"]
    if from_name:
        msg["From"] = f"{from_name} <{from_email}>"
    else:
        msg["From"] = from_email

    msg["To"] = to
    msg["Subject"] = subject

    if config.get("reply_to"):
        msg["Reply-To"] = config["reply_to"]

    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    if config["use_tls"]:
        with smtplib.SMTP(config["host"], config["port"], timeout=15) as server:
            server.starttls()
            server.login(config["user"], config["password"])
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(config["host"], config["port"], timeout=15) as server:
            server.login(config["user"], config["password"])
            server.send_message(msg)


# ------------------------------------------------------------
# Password reset email (unchanged signature, now passes org_id)
# ------------------------------------------------------------
def send_password_reset_email(
    to: str,
    reset_link: str,
    first_name: str = "",
    organization_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> None:
    greeting = f"Hi {first_name}," if first_name else "Hi,"
    subject = "Reset your Property Platform password"
    body = f"""{greeting}

We received a request to reset your Property Platform password.

Click this link to set a new password (expires in 1 hour):

{reset_link}

If you didn't request this, you can safely ignore this email.

— Property Platform
"""
    send_email(
        to=to,
        subject=subject,
        body=body,
        organization_id=organization_id,
        db=db,
    )