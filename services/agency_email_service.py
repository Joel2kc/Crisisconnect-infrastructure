import logging

from services.email_service import send_email_safe

logger = logging.getLogger(__name__)


async def send_agency_application_received_email(to: str, agency_name: str) -> None:
    await send_email_safe(
        to=to,
        subject="CrisisConnect - Application received",
        template_name="agency_application_received.html",
        context={"agency_name": agency_name},
    )


async def send_agency_verified_email(to: str, agency_name: str) -> None:
    await send_email_safe(
        to=to,
        subject="CrisisConnect - You're verified!",
        template_name="agency_verified.html",
        context={"agency_name": agency_name},
    )


async def send_agency_rejected_email(to: str, agency_name: str, reason: str) -> None:
    await send_email_safe(
        to=to,
        subject="CrisisConnect - Application update",
        template_name="agency_rejected.html",
        context={"agency_name": agency_name, "reason": reason},
    )

async def send_responder_added_email(
    to: str,
    full_name: str,
    agency_name: str,
    temporary_password: str,
) -> None:
    await send_email_safe(
        to=to,
        subject="CrisisConnect - You've been added",
        template_name="responder_added.html",
        context={
            "full_name": full_name,
            "email": to,
            "agency_name": agency_name,
            "temporary_password": temporary_password,
        },
    )
