import logging
import os
from pathlib import Path

from fastapi_mail import (
    ConnectionConfig,
    FastMail,
    MessageSchema,
    MessageType
)

logger = logging.getLogger(__name__)

TEMPLATE_FOLDER = Path(__file__).resolve().parent.parent / "templates" / "emails"

config = ConnectionConfig(
    MAIL_USERNAME=os.getenv("SMTP_USERNAME"),
    MAIL_PASSWORD=os.getenv("SMTP_PASSWORD"),
    MAIL_FROM=os.getenv("SMTP_FROM"),
    MAIL_FROM_NAME=os.getenv("SMTP_FROM_NAME"),
    MAIL_PORT=int(os.getenv("SMTP_PORT")),
    MAIL_SERVER=os.getenv("SMTP_HOST"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=TEMPLATE_FOLDER,
)

email_sender = FastMail(config)


async def send_email(to: str, subject: str, template_name: str, context: dict) -> None:
    """
    Sends a templated HTML email via fastapi-mail.
 
    template_name is the filename inside templates/emails/ (e.g.
    "agency_verified.html"). context is the dict of variables the
    template expects (see each template's {{ }} placeholders).
 
    This is async, call it via 'await' from an async caller, or hand it
    to FastAPI's BackgroundTasks directly (it supports async callables).
    """
    message = MessageSchema(
        subject=subject,
        recipients=[to],
        template_body=context,
        subtype=MessageType.html,
    )
    await email_sender.send_message(message, template_name=template_name)


async def send_email_safe(to: str, subject: str, template_name: str, context: dict) -> None:
    """
    Wraps send_email so a broken/misconfigured SMTP setup never surfaces
    as a failure on the request that triggered it - the agency/user record
    is already committed by the time this runs (called via BackgroundTasks).
    Logs the failure instead so it's visible without blocking anything.
    """
    try:
        await send_email(to=to, subject=subject, template_name=template_name, context=context)
    except Exception:
        logger.exception(f"Failed to send email to {to} (subject: {subject})")
