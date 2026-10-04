"""
Recording where an assignee is, and moving their status when the
geometry says so.
"""

import logging
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlmodel import Session, select

from db.models.incident_model import Incident, IncidentUpdate
from db.models.location_model import LocationPing
from db.models.responder_model import ResponderAssignment, ResponderProfile
from db.models.user_model import User
from db.models.volunteer_assignment_model import IncidentVolunteer
from db.models.volunteer_model import VolunteerProfile
from enums.location import AssigneeKind
from enums.responder import ResponderAssignmentStatus
from enums.volunteer_assignment import VolunteerAssignmentStatus
from schemas.location import LocationPingRead
from services.geofence import (
    CONFIRMATIONS_REQUIRED,
    distance_metres,
    has_arrived,
    has_departed,
    is_usable_fix,
    is_valid_coordinate,
)

logger = logging.getLogger(__name__)

MAX_PING_AGE = timedelta(minutes=15)

_RESPONDER_TRACKABLE = {
    ResponderAssignmentStatus.assigned,
    ResponderAssignmentStatus.en_route,
    ResponderAssignmentStatus.on_scene,
}
_VOLUNTEER_TRACKABLE = {
    VolunteerAssignmentStatus.accepted,
    VolunteerAssignmentStatus.en_route,
    VolunteerAssignmentStatus.on_scene,
}


def _load_responder_assignment(
    session: Session, assignment_id: int, actor: User
) -> tuple[ResponderAssignment, Incident]:
    assignment = session.get(ResponderAssignment, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found."
        )

    profile = session.get(ResponderProfile, assignment.responder_id)
   
    if not profile or profile.user_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only report your own location.",
        )

    return assignment, session.get(Incident, assignment.incident_id)


def _load_volunteer_assignment(
    session: Session, assignment_id: int, actor: User
) -> tuple[IncidentVolunteer, Incident]:
    assignment = session.get(IncidentVolunteer, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found."
        )

    profile = session.get(VolunteerProfile, assignment.volunteer_id)
    if not profile or profile.user_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only report your own location.",
        )

    return assignment, session.get(Incident, assignment.incident_id)


def _origin_for(
    session: Session, kind: AssigneeKind, assignment_id: int
) -> tuple[float, float] | None:
    """
    Where this assignee was when they were first tracked.

    Departure is measured from here rather than from the incident,
    because a responder who is already close to the scene would otherwise
    never register as having set off at all.
    """
    first = session.exec(
        select(LocationPing)
        .where(
            LocationPing.assignee_kind == kind,
            LocationPing.assignment_id == assignment_id,
        )
        .order_by(LocationPing.recorded_at)
    ).first()
    return (first.latitude, first.longitude) if first else None


def _consecutive_arrivals(
    session: Session,
    kind: AssigneeKind,
    assignment_id: int,
    incident: Incident,
    limit: int,
) -> int:
    """
    How many of the most recent fixes in a row were inside the radius.

    This is the debounce, and it is the difference between a feature that
    works and one nobody trusts. A single stray fix - which consumer GPS
    produces routinely - would otherwise flip someone to on_scene and the
    next fix would flip them back, filling the incident timeline with
    contradictions.
    """
    recent = session.exec(
        select(LocationPing)
        .where(
            LocationPing.assignee_kind == kind,
            LocationPing.assignment_id == assignment_id,
        )
        .order_by(LocationPing.recorded_at.desc())
        .limit(limit)
    ).all()

    streak = 0
    for ping in recent:
        if not is_usable_fix(ping.accuracy_m):
            break
        if has_arrived(
            incident.latitude,
            incident.longitude,
            ping.latitude,
            ping.longitude,
            ping.accuracy_m,
        ):
            streak += 1
        else:
            break
    return streak


def _log(session: Session, incident: Incident, note: str) -> None:
    session.add(
        IncidentUpdate(
            incident_id=incident.id,
            actor_id=None,
            note=note,
            old_status=incident.status,
            new_status=incident.status,
        )
    )


def record_ping(
    session: Session,
    kind: AssigneeKind,
    assignment_id: int,
    actor: User,
    latitude: float,
    longitude: float,
    accuracy_m: float | None,
    recorded_at: datetime | None,
) -> LocationPingRead:
    """
    Stores one position report and applies any status change it earns.

    Always stores the ping, even when it changes nothing - a fix that is
    too vague to act on is still evidence of where someone was.
    """
    if kind == AssigneeKind.responder:
        assignment, incident = _load_responder_assignment(
            session, assignment_id, actor
        )
        current = assignment.status
        trackable = current in _RESPONDER_TRACKABLE
    else:
        assignment, incident = _load_volunteer_assignment(
            session, assignment_id, actor
        )
        current = assignment.status
        trackable = current in _VOLUNTEER_TRACKABLE

    if not is_valid_coordinate(latitude, longitude):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Latitude and longitude are not a usable position.",
        )

   
    taken_at = recorded_at or datetime.utcnow()
    if taken_at.tzinfo is not None:
        taken_at = taken_at.replace(tzinfo=None)

    ping = LocationPing(
        incident_id=incident.id,
        assignee_kind=kind,
        assignment_id=assignment_id,
        latitude=latitude,
        longitude=longitude,
        accuracy_m=accuracy_m,
        recorded_at=taken_at,
    )

    has_incident_coords = is_valid_coordinate(incident.latitude, incident.longitude)
    if has_incident_coords:
        ping.distance_m = round(
            distance_metres(
                incident.latitude, incident.longitude, latitude, longitude
            ),
            1,
        )

    session.add(ping)
    session.flush()  # the debounce below has to see this ping

    new_status = None
    stale = datetime.utcnow() - taken_at > MAX_PING_AGE

    # Every reason to store the ping but not act on it, in one place.
    if (
        trackable
        and has_incident_coords
        and is_usable_fix(accuracy_m)
        and not stale
    ):
        if current in (
            ResponderAssignmentStatus.en_route,
            VolunteerAssignmentStatus.en_route,
        ):
            if (
                _consecutive_arrivals(
                    session, kind, assignment_id, incident, CONFIRMATIONS_REQUIRED
                )
                >= CONFIRMATIONS_REQUIRED
            ):
                new_status = (
                    ResponderAssignmentStatus.on_scene
                    if kind == AssigneeKind.responder
                    else VolunteerAssignmentStatus.on_scene
                )
        elif current in (
            ResponderAssignmentStatus.assigned,
            VolunteerAssignmentStatus.accepted,
        ):
            origin = _origin_for(session, kind, assignment_id)
         
            if (
                _consecutive_arrivals(
                    session, kind, assignment_id, incident, CONFIRMATIONS_REQUIRED
                )
                >= CONFIRMATIONS_REQUIRED
            ):
                new_status = (
                    ResponderAssignmentStatus.on_scene
                    if kind == AssigneeKind.responder
                    else VolunteerAssignmentStatus.on_scene
                )
            elif origin and has_departed(origin[0], origin[1], latitude, longitude):
                new_status = (
                    ResponderAssignmentStatus.en_route
                    if kind == AssigneeKind.responder
                    else VolunteerAssignmentStatus.en_route
                )

    if new_status is not None:
        assignment.status = new_status
        ping.triggered_transition = True

        if kind == AssigneeKind.responder and assignment.started_at is None:
            assignment.started_at = datetime.utcnow()

        who = session.get(User, _user_id_for(session, kind, assignment))
        label = "en route" if "en_route" in new_status.value else "on scene"
        _log(
            session,
            incident,
            f"{who.full_name} automatically marked {label} "
            f"({ping.distance_m:.0f}m from the scene).",
        )
        session.add(assignment)

    session.commit()
    session.refresh(ping)

    return LocationPingRead(
        id=ping.id,
        incident_id=ping.incident_id,
        assignment_id=assignment_id,
        assignee_kind=kind,
        latitude=ping.latitude,
        longitude=ping.longitude,
        accuracy_m=ping.accuracy_m,
        distance_m=ping.distance_m,
        recorded_at=ping.recorded_at,
        assignment_status=assignment.status.value,
        status_changed=new_status is not None,
        tracking_active=trackable and has_incident_coords,
    )


def _user_id_for(session: Session, kind: AssigneeKind, assignment) -> int:
    if kind == AssigneeKind.responder:
        return session.get(ResponderProfile, assignment.responder_id).user_id
    return session.get(VolunteerProfile, assignment.volunteer_id).user_id


def latest_positions(
    session: Session, incident_id: int
) -> list[LocationPingRead]:
    """
    The most recent fix for everyone currently attending this incident.

    One row per assignee rather than the whole trail - this feeds a
    dispatcher's map, which only ever needs where people are now.
    """
    pings = session.exec(
        select(LocationPing)
        .where(LocationPing.incident_id == incident_id)
        .order_by(LocationPing.recorded_at.desc())
    ).all()

    seen: set[tuple[str, int]] = set()
    latest = []
    for ping in pings:
        key = (ping.assignee_kind.value, ping.assignment_id)
        if key in seen:
            continue
        seen.add(key)
        latest.append(
            LocationPingRead(
                id=ping.id,
                incident_id=ping.incident_id,
                assignment_id=ping.assignment_id,
                assignee_kind=ping.assignee_kind,
                latitude=ping.latitude,
                longitude=ping.longitude,
                accuracy_m=ping.accuracy_m,
                distance_m=ping.distance_m,
                recorded_at=ping.recorded_at,
                assignment_status=None,
                status_changed=False,
                tracking_active=True,
            )
        )
    return latest
