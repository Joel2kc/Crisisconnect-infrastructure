
import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlmodel import Session, select

from db.models.agency_model import Agency
from db.models.ai_model import IncidentAnalysis
from db.models.incident_model import Incident, IncidentAgency, IncidentUpdate
from db.models.user_model import User
from db.models.volunteer_assignment_model import IncidentVolunteer
from db.models.volunteer_model import VolunteerProfile
from enums.user import UserRole
from enums.volunteer_assignment import VolunteerAssignmentStatus
from schemas.volunteer_assignment import (
    VolunteerAssignmentDashboardItem,
    VolunteerAssignmentRead,
)

logger = logging.getLogger(__name__)

_INVITE_ROLES = {
    UserRole.agency_admin,
    UserRole.agency_dispatcher,
    UserRole.crisis_connect_admin,
}

# An invitation in one of these states is live - the volunteer is either
# still deciding or has said yes. Re-inviting them would be noise.
_OPEN = {VolunteerAssignmentStatus.invited, VolunteerAssignmentStatus.accepted}


def _get_incident_or_404(session: Session, incident_id: int) -> Incident:
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found."
        )
    return incident


def _authorize_invite(session: Session, incident_id: int, actor: User) -> int:
    """
    Returns the agency id the invitation will be recorded against.

    Checked against IncidentAgency rather than role alone, the same rule
    responder dispatch uses: an agency must actually have the incident
    before it can call anyone to it.
    """
    if actor.role not in _INVITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to invite volunteers.",
        )

    links = session.exec(
        select(IncidentAgency).where(IncidentAgency.incident_id == incident_id)
    ).all()

    if actor.role == UserRole.crisis_connect_admin:
        if not links:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This incident has not been routed to any agency, so "
                    "there is no agency to invite on behalf of."
                ),
            )
        return links[0].agency_id

    if not actor.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not linked to an agency.",
        )

    if actor.agency_id not in {link.agency_id for link in links}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This incident is not routed to your agency.",
        )
    return actor.agency_id


def _to_read(
    assignment: IncidentVolunteer, user: User
) -> VolunteerAssignmentRead:
    return VolunteerAssignmentRead(
        id=assignment.id,
        incident_id=assignment.incident_id,
        agency_id=assignment.agency_id,
        volunteer_id=assignment.volunteer_id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        status=assignment.status,
        matched_skills=assignment.matched_skills or [],
        note=assignment.note,
        response_note=assignment.response_note,
        invited_by=assignment.invited_by,
        invited_at=assignment.invited_at,
        responded_at=assignment.responded_at,
        completed_at=assignment.completed_at,
    )


def _matched_skills_for(
    session: Session, incident_id: int, volunteer_id: int
) -> list[str]:
    """
    The skills that made this volunteer a candidate, captured now.

    Recomputed from the stored analysis rather than trusted from the
    client, then frozen onto the row: re-running the analysis later must
    not rewrite the reason a dispatcher acted at the time.
    """
    from services.incident_recommendation_service import _resolve_skills

    analysis = session.exec(
        select(IncidentAnalysis).where(IncidentAnalysis.incident_id == incident_id)
    ).first()
    if not analysis or not analysis.suggested_skills:
        return []

    skill_names, _, _ = _resolve_skills(session, analysis.suggested_skills)
    if not skill_names:
        return []

    from db.models.volunteer_model import VolunteerSkill

    links = session.exec(
        select(VolunteerSkill).where(
            VolunteerSkill.volunteer_id == volunteer_id,
            VolunteerSkill.skill_id.in_(list(skill_names)),
        )
    ).all()
    return sorted(skill_names[link.skill_id] for link in links)


def invite_volunteer(
    session: Session,
    incident_id: int,
    volunteer_id: int,
    actor: User,
    note: str | None = None,
) -> tuple[VolunteerAssignmentRead, Incident, Agency, list[str]]:
    """
    Invites one volunteer to one incident.

    Returns everything the caller needs to compose the volunteer's
    notification: the assignment, the incident, the inviting agency, and
    the hazards from the analysis.
    """
    incident = _get_incident_or_404(session, incident_id)
    agency_id = _authorize_invite(session, incident_id, actor)

    profile = session.get(VolunteerProfile, volunteer_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found."
        )

    volunteer_user = session.get(User, profile.user_id)
    if not volunteer_user or not volunteer_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This volunteer's account is not active.",
        )

    # verified is the platform's only quality gate on a volunteer. An
    # unverified profile is a stranger who filled in a form, and this
    # sends someone to an emergency.
    if not profile.verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This volunteer has not been verified.",
        )

    existing = session.exec(
        select(IncidentVolunteer).where(
            IncidentVolunteer.incident_id == incident_id,
            IncidentVolunteer.volunteer_id == volunteer_id,
            IncidentVolunteer.status.in_(list(_OPEN)),
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This volunteer already has an open invitation to this "
                f"incident (status: {existing.status.value})."
            ),
        )

    assignment = IncidentVolunteer(
        incident_id=incident_id,
        volunteer_id=volunteer_id,
        agency_id=agency_id,
        invited_by=actor.id,
        status=VolunteerAssignmentStatus.invited,
        matched_skills=_matched_skills_for(session, incident_id, volunteer_id),
        note=note,
    )
    session.add(assignment)
    session.add(
        IncidentUpdate(
            incident_id=incident_id,
            actor_id=actor.id,
            note=f"Volunteer {volunteer_user.full_name} invited.",
            # The incident's own status is unchanged - incident_service
            # owns that lifecycle. new_status is NOT NULL, so it repeats
            # the current value rather than claiming a transition.
            old_status=incident.status,
            new_status=incident.status,
        )
    )
    session.commit()
    session.refresh(assignment)

    analysis = session.exec(
        select(IncidentAnalysis).where(IncidentAnalysis.incident_id == incident_id)
    ).first()
    hazards = (analysis.hazards or []) if analysis else []

    return (
        _to_read(assignment, volunteer_user),
        incident,
        session.get(Agency, agency_id),
        hazards,
    )


def list_incident_volunteers(
    session: Session, incident_id: int, actor: User
) -> list[VolunteerAssignmentRead]:
    _get_incident_or_404(session, incident_id)
    _authorize_invite(session, incident_id, actor)

    assignments = session.exec(
        select(IncidentVolunteer)
        .where(IncidentVolunteer.incident_id == incident_id)
        .order_by(IncidentVolunteer.invited_at)
    ).all()

    result = []
    for assignment in assignments:
        profile = session.get(VolunteerProfile, assignment.volunteer_id)
        user = session.get(User, profile.user_id)
        result.append(_to_read(assignment, user))
    return result


def stand_down_volunteer(
    session: Session, incident_id: int, assignment_id: int, actor: User
) -> VolunteerAssignmentRead:
    """
    Withdraws an invitation.

    Kept as a status rather than a deletion: a volunteer who was called
    and then told not to come should still be able to see that on their
    dashboard, instead of the invitation silently disappearing.
    """
    incident = _get_incident_or_404(session, incident_id)
    _authorize_invite(session, incident_id, actor)

    assignment = session.get(IncidentVolunteer, assignment_id)
    if not assignment or assignment.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found."
        )

    if assignment.status not in _OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This invitation is already '{assignment.status.value}'.",
        )

    profile = session.get(VolunteerProfile, assignment.volunteer_id)
    volunteer_user = session.get(User, profile.user_id)

    assignment.status = VolunteerAssignmentStatus.stood_down
    session.add(assignment)
    session.add(
        IncidentUpdate(
            incident_id=incident_id,
            actor_id=actor.id,
            note=f"Volunteer {volunteer_user.full_name} stood down.",
            old_status=incident.status,
            new_status=incident.status,
        )
    )
    session.commit()
    session.refresh(assignment)
    return _to_read(assignment, volunteer_user)


def complete_volunteer_assignment(
    session: Session, incident_id: int, assignment_id: int, actor: User
) -> VolunteerAssignmentRead:
    incident = _get_incident_or_404(session, incident_id)
    _authorize_invite(session, incident_id, actor)

    assignment = session.get(IncidentVolunteer, assignment_id)
    if not assignment or assignment.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found."
        )

    if assignment.status != VolunteerAssignmentStatus.accepted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an accepted invitation can be completed.",
        )

    profile = session.get(VolunteerProfile, assignment.volunteer_id)
    volunteer_user = session.get(User, profile.user_id)

    assignment.status = VolunteerAssignmentStatus.completed
    assignment.completed_at = datetime.utcnow()
    session.add(assignment)
    session.add(
        IncidentUpdate(
            incident_id=incident_id,
            actor_id=actor.id,
            note=f"Volunteer {volunteer_user.full_name} completed their assignment.",
            old_status=incident.status,
            new_status=incident.status,
        )
    )
    session.commit()
    session.refresh(assignment)
    return _to_read(assignment, volunteer_user)


# --------------------------------------------------------------------
# Volunteer side: their own dashboard.
# --------------------------------------------------------------------


def _profile_for(session: Session, actor: User) -> VolunteerProfile:
    profile = session.exec(
        select(VolunteerProfile).where(VolunteerProfile.user_id == actor.id)
    ).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account does not have a volunteer profile.",
        )
    return profile


def list_my_assignments(
    session: Session, actor: User, open_only: bool = False
) -> list[VolunteerAssignmentDashboardItem]:
    """
    The volunteer's own dashboard.

    Scoped by the profile belonging to the signed-in user, so a volunteer
    can only ever see invitations addressed to them - there is no
    volunteer_id parameter to tamper with.
    """
    profile = _profile_for(session, actor)

    query = select(IncidentVolunteer).where(
        IncidentVolunteer.volunteer_id == profile.id
    )
    if open_only:
        query = query.where(IncidentVolunteer.status.in_(list(_OPEN)))

    assignments = session.exec(
        query.order_by(IncidentVolunteer.invited_at.desc())
    ).all()

    items = []
    for assignment in assignments:
        incident = session.get(Incident, assignment.incident_id)
        agency = session.get(Agency, assignment.agency_id)
        analysis = session.exec(
            select(IncidentAnalysis).where(
                IncidentAnalysis.incident_id == assignment.incident_id
            )
        ).first()

        items.append(
            VolunteerAssignmentDashboardItem(
                id=assignment.id,
                incident_id=assignment.incident_id,
                status=assignment.status,
                agency_name=agency.name if agency else "Unknown agency",
                reference_code=incident.reference_code,
                emergency_type=incident.emergency_type,
                severity=incident.severity,
                location=incident.location,
                description=incident.description,
                occurred_at=incident.occurred_at,
                # Shown before they answer, not after. A volunteer
                # accepting blind is the outcome worth designing out.
                hazards=(analysis.hazards or []) if analysis else [],
                matched_skills=assignment.matched_skills or [],
                note=assignment.note,
                invited_at=assignment.invited_at,
                responded_at=assignment.responded_at,
            )
        )
    return items


def respond_to_assignment(
    session: Session,
    assignment_id: int,
    actor: User,
    accept: bool,
    response_note: str | None = None,
) -> tuple[VolunteerAssignmentDashboardItem, dict]:
    """
    The volunteer accepts or declines.

    Only the invited volunteer can call this, and only while the
    invitation is still open. Declining is a normal outcome and is
    recorded as such - it is the answer that lets a dispatcher move on to
    the next person.

    Returns the updated dashboard card plus everything the caller needs
    to notify the inviting agency, gathered here while the session is
    still open.
    """
    profile = _profile_for(session, actor)

    assignment = session.get(IncidentVolunteer, assignment_id)
    if not assignment or assignment.volunteer_id != profile.id:
        # 404 rather than 403: a volunteer has no business learning that
        # an invitation exists for someone else.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found."
        )

    if assignment.status != VolunteerAssignmentStatus.invited:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You have already responded to this invitation "
                f"(status: {assignment.status.value})."
            ),
        )

    assignment.status = (
        VolunteerAssignmentStatus.accepted
        if accept
        else VolunteerAssignmentStatus.declined
    )
    assignment.response_note = response_note
    assignment.responded_at = datetime.utcnow()
    session.add(assignment)

    incident = session.get(Incident, assignment.incident_id)
    verb = "accepted" if accept else "declined"
    session.add(
        IncidentUpdate(
            incident_id=assignment.incident_id,
            actor_id=actor.id,
            note=f"Volunteer {actor.full_name} {verb} the invitation.",
            old_status=incident.status,
            new_status=incident.status,
        )
    )
    session.commit()

    notification = {
        "agency_id": assignment.agency_id,
        "volunteer_name": actor.full_name,
        "phone": actor.phone,
        "accepted": accept,
        "response_note": response_note,
        "matched_skills": assignment.matched_skills or [],
        "incident": incident,
    }

    items = list_my_assignments(session, actor)
    item = next(item for item in items if item.id == assignment_id)
    return item, notification
