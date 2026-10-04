import logging

from sqlmodel import Session, select

from db.models.agency_model import Agency
from db.models.incident_model import Incident, IncidentAgency
from db.models.user_model import User
from enums.user import UserRole
from services.email_service import send_email_safe

logger = logging.getLogger(__name__)


_NOTIFIED_ROLES = [UserRole.agency_admin, UserRole.agency_dispatcher]


def collect_agency_recipients(session: Session, agency_id: int) -> list[str]:
    """
    The email addresses to use for one agency.

    Active admins and dispatchers, falling back to Agency.email when the
    agency has neither - common right after onboarding, since the agency
    admin stays inactive until the agency is verified.
    """
    agency = session.get(Agency, agency_id)
    if not agency:
        return []

    staff = session.exec(
        select(User).where(
            User.agency_id == agency_id,
            User.role.in_(_NOTIFIED_ROLES),
            User.is_active == True,  # noqa: E712 - SQL, not Python
        )
    ).all()

    targets = [user.email for user in staff if user.email]
    if targets:
        return targets
    return [agency.email] if agency.email else []


def collect_incident_recipients(
    session: Session, incident_id: int
) -> list[tuple[str, str]]:
    """
    Returns (email, agency_name) for everyone who should hear about this
    incident.

    Falls back to Agency.email when an agency has no active admin or
    dispatcher account, which is common right after onboarding: the
    agency admin stays inactive until the agency is verified, so without
    this the first incidents would reach nobody at all.
    """
    links = session.exec(
        select(IncidentAgency).where(IncidentAgency.incident_id == incident_id)
    ).all()

    recipients: list[tuple[str, str]] = []
    seen: set[str] = set()

    for link in links:
        agency = session.get(Agency, link.agency_id)
        if not agency:
            continue

        targets = collect_agency_recipients(session, agency.id)
        if not targets:
            logger.warning(
                "incident %s routed to agency %s with no contactable recipient",
                incident_id,
                agency.id,
            )

        for email in targets:
            if email and email not in seen:
                seen.add(email)
                recipients.append((email, agency.name))

    return recipients


def incident_context(incident: Incident) -> dict:
    return {
        "reference_code": incident.reference_code,
        "emergency_type": incident.emergency_type.value.replace("_", " ").title(),
        "severity": incident.severity.value.replace("_", " ").title(),
        "location": incident.location,
        "description": incident.description,
        "occurred_at": incident.occurred_at.strftime("%d %b %Y, %H:%M"),
    }


async def send_incident_routed_email(
    to: str, agency_name: str, context: dict
) -> None:
    await send_email_safe(
        to=to,
        # The reference code is in the subject so a dispatcher can find
        # the thread again without opening it.
        subject=(
            f"CrisisConnect - New {context['severity']} incident "
            f"{context['reference_code']}"
        ),
        template_name="incident_routed.html",
        context={"agency_name": agency_name, **context},
    )


async def send_responder_assigned_email(
    to: str, full_name: str, hazards: list[str], context: dict
) -> None:
    await send_email_safe(
        to=to,
        subject=(
            f"CrisisConnect - You have been dispatched to "
            f"{context['reference_code']}"
        ),
        template_name="responder_assigned.html",
        # Hazards come from the AI analysis when one exists. Nobody should
        # arrive at live power lines without having been told.
        context={"full_name": full_name, "hazards": hazards, **context},
    )


async def send_volunteer_invited_email(
    to: str,
    full_name: str,
    agency_name: str,
    hazards: list[str],
    note: str | None,
    context: dict,
) -> None:
    """
    Asks a volunteer to attend. Deliberately worded as a request.

    Hazards are included for the same reason as the responder email, but
    the stakes are higher: this is a member of the public, not trained
    staff, and they are being asked to decide. Accepting blind is the
    outcome this is designed to prevent.
    """
    await send_email_safe(
        to=to,
        subject=(
            f"CrisisConnect - {agency_name} needs your help "
            f"({context['reference_code']})"
        ),
        template_name="volunteer_invited.html",
        context={
            "full_name": full_name,
            "agency_name": agency_name,
            "hazards": hazards,
            "note": note,
            **context,
        },
    )


async def send_volunteer_response_email(
    to: str,
    volunteer_name: str,
    accepted: bool,
    response_note: str | None,
    matched_skills: list[str],
    phone: str | None,
    context: dict,
) -> None:
    """
    Tells the inviting agency how a volunteer answered.

    A decline matters as much as an acceptance, and arguably more: it is
    what tells a dispatcher to stop waiting and call the next person. The
    answer is in the subject line so it can be read without opening the
    message.
    """
    answer = "accepted" if accepted else "declined"
    await send_email_safe(
        to=to,
        subject=(
            f"CrisisConnect - {volunteer_name} {answer} "
            f"({context['reference_code']})"
        ),
        template_name="volunteer_response.html",
        context={
            "volunteer_name": volunteer_name,
            "accepted": accepted,
            "response_note": response_note,
            "matched_skills": matched_skills,
            "phone": phone,
            **context,
        },
    )
