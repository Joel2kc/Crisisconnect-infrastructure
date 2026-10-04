"""
Dispatching an agency's responders to an incident.

This is the step that turns the recommendation panel into an action. The
panel ranks who could go; this records who was actually sent, and by
whom - ResponderAssignment.assigned_by is NOT NULL and has no default,
so every row names the person who made the call. No AI code path can
produce one, because no AI code path has a user id.

A responder's availability is maintained here rather than being set by
hand: assigning marks them 'assigned', completing puts them back to
'available'. That keeps the field the recommendation ranking sorts on
honest without anyone having to remember to update it.
"""

import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlmodel import Session, select

from db.models.incident_model import Incident, IncidentAgency, IncidentUpdate
from db.models.responder_model import ResponderAssignment, ResponderProfile
from db.models.user_model import User
from enums.responder import ResponderAssignmentStatus, ResponderAvailabilityStatus
from enums.user import UserRole
from schemas.responder_assignment import ResponderAssignmentRead

logger = logging.getLogger(__name__)


_DISPATCH_ROLES = {
    UserRole.agency_admin,
    UserRole.agency_dispatcher,
    UserRole.crisis_connect_admin,
}

_TERMINAL = {ResponderAssignmentStatus.complete}


def _get_incident_or_404(session: Session, incident_id: int) -> Incident:
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found."
        )
    return incident


def _authorize_dispatch(session: Session, incident_id: int, actor: User) -> None:
    """
    Only an agency the incident was actually routed to may dispatch to it.

    Checked against IncidentAgency rather than role alone: being an
    agency_dispatcher somewhere does not entitle you to send responders
    to another agency's incident.
    """
    if actor.role not in _DISPATCH_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to dispatch responders.",
        )

    if actor.role == UserRole.crisis_connect_admin:
        return

    if not actor.agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not linked to an agency.",
        )

    linked = session.exec(
        select(IncidentAgency).where(
            IncidentAgency.incident_id == incident_id,
            IncidentAgency.agency_id == actor.agency_id,
        )
    ).first()

    if not linked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This incident is not routed to your agency.",
        )


def _to_read(
    assignment: ResponderAssignment, profile: ResponderProfile, user: User
) -> ResponderAssignmentRead:
    return ResponderAssignmentRead(
        id=assignment.id,
        incident_id=assignment.incident_id,
        responder_id=assignment.responder_id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        position=profile.position,
        employee_id=profile.employee_id,
        availability_status=profile.availability_status,
        status=assignment.status,
        response_outcome=assignment.response_outcome,
        response_note=assignment.response_note,
        assigned_by=assignment.assigned_by,
        assigned_at=assignment.assigned_at,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,
    )


def _load(
    session: Session, assignment: ResponderAssignment
) -> ResponderAssignmentRead:
    profile = session.get(ResponderProfile, assignment.responder_id)
    user = session.get(User, profile.user_id)
    return _to_read(assignment, profile, user)


def assign_responder(
    session: Session, incident_id: int, responder_id: int, actor: User
) -> tuple[ResponderAssignmentRead, Incident]:
    """
    Sends one responder to one incident.

    Returns the assignment and the incident, because the caller needs
    the incident's details to compose the responder's notification.
    """
    incident = _get_incident_or_404(session, incident_id)
    _authorize_dispatch(session, incident_id, actor)

    profile = session.get(ResponderProfile, responder_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Responder not found."
        )

    responder_user = session.get(User, profile.user_id)
    if not responder_user or not responder_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This responder's account is not active.",
        )

    dispatching_agency_id = (
        responder_user.agency_id
        if actor.role == UserRole.crisis_connect_admin
        else actor.agency_id
    )
    if responder_user.agency_id != dispatching_agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This responder belongs to a different agency.",
        )

    linked = session.exec(
        select(IncidentAgency).where(
            IncidentAgency.incident_id == incident_id,
            IncidentAgency.agency_id == dispatching_agency_id,
        )
    ).first()
    if not linked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This responder's agency is not routed to this incident.",
        )

    existing = session.exec(
        select(ResponderAssignment).where(
            ResponderAssignment.incident_id == incident_id,
            ResponderAssignment.responder_id == responder_id,
            ResponderAssignment.status != ResponderAssignmentStatus.complete,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This responder is already assigned to this incident.",
        )

    assignment = ResponderAssignment(
        incident_id=incident_id,
        responder_id=responder_id,
        assigned_by=actor.id,
        status=ResponderAssignmentStatus.assigned,
    )
    session.add(assignment)

    profile.availability_status = ResponderAvailabilityStatus.assigned
    profile.updated_at = datetime.utcnow()
    session.add(profile)

    session.add(
        IncidentUpdate(
            incident_id=incident_id,
            actor_id=actor.id,
            note=f"{responder_user.full_name} assigned as responder.",
            old_status=incident.status,
            new_status=incident.status,
        )
    )

    session.commit()
    session.refresh(assignment)
    session.refresh(profile)

    return _to_read(assignment, profile, responder_user), incident


def list_assignments(
    session: Session, incident_id: int, actor: User
) -> list[ResponderAssignmentRead]:
    _get_incident_or_404(session, incident_id)
    _authorize_dispatch(session, incident_id, actor)

    assignments = session.exec(
        select(ResponderAssignment)
        .where(ResponderAssignment.incident_id == incident_id)
        .order_by(ResponderAssignment.assigned_at)
    ).all()

    return [_load(session, assignment) for assignment in assignments]


def update_assignment_status(
    session: Session,
    incident_id: int,
    assignment_id: int,
    new_status: ResponderAssignmentStatus,
    actor: User,
) -> ResponderAssignmentRead:
    """
    Moves an assignment along: assigned -> en_route -> on_scene -> complete.

    Updates the operational status of an assignment.

    Completion is handled separately through the completion endpoint because
    a completed response requires an outcome, response note, and proof of
    response.

    Order is not enforced. Real incidents skip steps, and a responder who
    arrives before anyone updates the record should not be blocked from
    being marked on_scene. Only the terminal state is protected.
    """
    incident = _get_incident_or_404(session, incident_id)
    # _authorize_dispatch(session, incident_id, actor)

    assignment = session.get(ResponderAssignment, assignment_id)
    if not assignment or assignment.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found."
        )
    
    _authorize_assignment_status_update(session, assignment, actor)

    if assignment.status in _TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This assignment is already complete and cannot be changed.",
        )
    # if new_status == ResponderAssignmentStatus.complete:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Use the completion endpoint to complete a response.",
    #     )

    profile = session.get(ResponderProfile, assignment.responder_id)
    responder_user = session.get(User, profile.user_id)

    assignment.status = new_status

    if (
        assignment.started_at is None
        and new_status != ResponderAssignmentStatus.assigned
    ):
       
        assignment.started_at = datetime.utcnow()

    if new_status == ResponderAssignmentStatus.complete:
        assignment.completed_at = datetime.utcnow()
       
        still_busy = session.exec(
            select(ResponderAssignment).where(
                ResponderAssignment.responder_id == assignment.responder_id,
                ResponderAssignment.id != assignment.id,
                ResponderAssignment.status != ResponderAssignmentStatus.complete,
            )
        ).first()
        if not still_busy:
            profile.availability_status = ResponderAvailabilityStatus.available
            profile.updated_at = datetime.utcnow()
            session.add(profile)

    session.add(assignment)
    session.add(
        IncidentUpdate(
            incident_id=incident_id,
            actor_id=actor.id,
            note=f"{responder_user.full_name} is now {new_status.value.replace('_', ' ')}.",
            old_status=incident.status,
            new_status=incident.status,
        )
    )

    session.commit()
    session.refresh(assignment)
    session.refresh(profile)
    return _to_read(assignment, profile, responder_user)


def cancel_assignment(
    session: Session, incident_id: int, assignment_id: int, actor: User
) -> None:
    """
    Undoes a dispatch that has not started yet.

    Deliberately narrow: only while the status is still 'assigned'. Once
    a responder is en route the assignment is part of the incident's
    history and gets closed with 'complete', not erased.
    """
    incident = _get_incident_or_404(session, incident_id)
    _authorize_dispatch(session, incident_id, actor)

    assignment = session.get(ResponderAssignment, assignment_id)
    if not assignment or assignment.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found."
        )

    if assignment.status != ResponderAssignmentStatus.assigned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only an assignment that has not started can be cancelled. "
                "Mark it complete instead."
            ),
        )

    profile = session.get(ResponderProfile, assignment.responder_id)
    responder_user = session.get(User, profile.user_id)

    session.delete(assignment)

    still_busy = session.exec(
        select(ResponderAssignment).where(
            ResponderAssignment.responder_id == assignment.responder_id,
            ResponderAssignment.id != assignment.id,
            ResponderAssignment.status != ResponderAssignmentStatus.complete,
        )
    ).first()
    if not still_busy:
        profile.availability_status = ResponderAvailabilityStatus.available
        profile.updated_at = datetime.utcnow()
        session.add(profile)

    session.add(
        IncidentUpdate(
            incident_id=incident_id,
            actor_id=actor.id,
            note=f"{responder_user.full_name} stood down before dispatch.",
            old_status=incident.status,
            new_status=incident.status,
        )
    )
    session.commit()

def _authorize_assignment_status_update(
    session: Session,
    assignment: ResponderAssignment,
    actor: User,
) -> None:

    if actor.role in _DISPATCH_ROLES:
        _authorize_dispatch(
            session,
            assignment.incident_id,
            actor,
        )
        return

    if actor.role == UserRole.responder:
        profile = session.exec(
            select(ResponderProfile).where(
                ResponderProfile.user_id == actor.id
            )
        ).first()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Responder profile not found.",
            )

        if assignment.responder_id != profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own assignment.",
            )

        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to update this assignment.",
    )
