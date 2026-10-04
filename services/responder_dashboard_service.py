from datetime import datetime, timedelta

from fastapi import HTTPException, status, UploadFile
from sqlmodel import Session, select, func

from db.models.incident_model import Incident, IncidentMedia, IncidentUpdate
from db.models.responder_model import (
    ResponderAssignment,
    ResponderProfile,
    ResponderCompletionEvidence,
)
from db.models.user_model import User
from enums.responder import (
    ResponderAssignmentFilter,
    ResponderAssignmentStatus,
    ResponderResponseOutcome,
    ResponderAvailabilityStatus,
)
from schemas.responder_dashboard import (
    ResponderAssignmentListItem,
    ResponderAssignmentsResponse,
    ResponderAssignmentDetails,
    ResponderDashboardResponse,
    ResponderTeamMember,
)
from schemas.responder import ResponderCompletionEvidenceRead, ResponderCompletionResponse
from schemas.incident import IncidentMediaRead
from services.file_storage_service import (
    generate_presigned_url,
    upload_response_evidence_to_s3,
)
from services.responder_assignment_service import _get_incident_or_404, _to_read


_ACTIVE_STATUSES = {
    ResponderAssignmentStatus.assigned,
    ResponderAssignmentStatus.en_route,
    ResponderAssignmentStatus.on_scene,
}


def _get_responder_profile(
    session: Session,
    current_user: User,
) -> ResponderProfile:
    profile = session.exec(
        select(ResponderProfile).where(
            ResponderProfile.user_id == current_user.id
        )
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Responder profile not found.",
        )

    return profile

def _to_assignment_item(
    assignment: ResponderAssignment,
    incident: Incident,
) -> ResponderAssignmentListItem:
    return ResponderAssignmentListItem(
        assignment_id=assignment.id,
        incident_id=incident.id,
        reference_code=incident.reference_code,
        emergency_type=incident.emergency_type,
        emergency_type_other=incident.emergency_type_other,
        location=incident.location,
        severity=incident.severity,
        incident_status=incident.status,
        assignment_status=assignment.status,
        assigned_at=assignment.assigned_at,
        completed_at=assignment.completed_at,
    )


def list_my_assignments(
    session: Session,
    current_user: User,
    page: int = 1,
    limit: int = 20,
    status_filter: ResponderAssignmentFilter | None = None,
) -> ResponderAssignmentsResponse:

    profile = _get_responder_profile(session, current_user)

    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be greater than 0.",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100.",
        )

    base_query = (
        select(ResponderAssignment, Incident)
        .join(
            Incident,
            ResponderAssignment.incident_id == Incident.id,
        )
        .where(
            ResponderAssignment.responder_id == profile.id
        )
    )

    if status_filter == ResponderAssignmentFilter.active:
        base_query = base_query.where(
            ResponderAssignment.status.in_(_ACTIVE_STATUSES)
        )

    elif status_filter == ResponderAssignmentFilter.completed:
        base_query = base_query.where(
            ResponderAssignment.status
            == ResponderAssignmentStatus.complete
        )

    count_query = select(func.count()).select_from(
        base_query.subquery()
    )

    total = session.exec(count_query).one()

    offset = (page - 1) * limit

    rows = session.exec(
        base_query
        .order_by(ResponderAssignment.assigned_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    assignments = [
        _to_assignment_item(assignment, incident)
        for assignment, incident in rows
    ]

    # Counts for the tabs.
    active_count = session.exec(
        select(func.count(ResponderAssignment.id)).where(
            ResponderAssignment.responder_id == profile.id,
            ResponderAssignment.status.in_(_ACTIVE_STATUSES),
        )
    ).one()

    completed_count = session.exec(
        select(func.count(ResponderAssignment.id)).where(
            ResponderAssignment.responder_id == profile.id,
            ResponderAssignment.status
            == ResponderAssignmentStatus.complete,
        )
    ).one()

    total_pages = (total + limit - 1) // limit

    return ResponderAssignmentsResponse(
        assignments=assignments,
        active_count=active_count,
        completed_count=completed_count,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


def get_my_assignment_details(
    session: Session,
    current_user: User,
    assignment_id: int,
) -> ResponderAssignmentDetails:

    profile = _get_responder_profile(session, current_user)

    row = session.exec(
        select(ResponderAssignment, Incident)
        .join(
            Incident,
            ResponderAssignment.incident_id == Incident.id,
        )
        .where(
            ResponderAssignment.id == assignment_id,
            ResponderAssignment.responder_id == profile.id,
        )
    ).first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found.",
        )

    assignment, incident = row

    media = session.exec(
        select(IncidentMedia)
        .where(IncidentMedia.incident_id == incident.id)
        .order_by(IncidentMedia.uploaded_at)
    ).all()

    media_data = [
        IncidentMediaRead(
            id=item.id,
            incident_id=item.incident_id,
            uploaded_by=item.uploaded_by,
            url=generate_presigned_url(item.url),
            uploaded_at=item.uploaded_at,
        )
        for item in media
    ]

    team_rows = session.exec(
        select(
            ResponderAssignment,
            ResponderProfile,
            User,
        )
        .join(
            ResponderProfile,
            ResponderAssignment.responder_id == ResponderProfile.id,
        )
        .join(
            User,
            ResponderProfile.user_id == User.id,
        )
        .where(
            ResponderAssignment.incident_id == incident.id,
        )
    ).all()

    response_team = [
        ResponderTeamMember(
            responder_id=profile_row.id,
            full_name=user.full_name,
            position=profile_row.position,
            employee_id=profile_row.employee_id,
            assignment_status=team_assignment.status,
        )
        for team_assignment, profile_row, user in team_rows
    ]

    return ResponderAssignmentDetails(
        assignment_id=assignment.id,

        incident_id=incident.id,
        reference_code=incident.reference_code,

        emergency_type=incident.emergency_type,
        emergency_type_other=incident.emergency_type_other,
        description=incident.description,
        location=incident.location,
        severity=incident.severity,
        incident_status=incident.status,
        occurred_at=incident.occurred_at,
        reported_at=incident.created_at,

        assignment_status=assignment.status,
        assigned_at=assignment.assigned_at,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,

        media=media_data,
        response_team=response_team,
    )


def get_responder_dashboard(
    session: Session,
    current_user: User,
) -> ResponderDashboardResponse:

    profile = _get_responder_profile(session, current_user)

    # All active assignments belonging to this responder.
    active_rows = session.exec(
        select(ResponderAssignment, Incident)
        .join(
            Incident,
            ResponderAssignment.incident_id == Incident.id,
        )
        .where(
            ResponderAssignment.responder_id == profile.id,
            ResponderAssignment.status.in_(_ACTIVE_STATUSES),
        )
        .order_by(ResponderAssignment.assigned_at.desc())
    ).all()

    active_responses = [
        _to_assignment_item(assignment, incident)
        for assignment, incident in active_rows
    ]

    # Total active assignments.
    active_count = len(active_responses)

    # Total completed assignments.
    completed_count = session.exec(
        select(func.count(ResponderAssignment.id)).where(
            ResponderAssignment.responder_id == profile.id,
            ResponderAssignment.status
            == ResponderAssignmentStatus.complete,
        )
    ).one()

    # Start of today in UTC.
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    start_of_tomorrow = start_of_day + timedelta(days=1)

    today_rows = session.exec(
        select(ResponderAssignment, Incident)
        .join(
            Incident,
            ResponderAssignment.incident_id == Incident.id,
        )
        .where(
            ResponderAssignment.responder_id == profile.id,
            ResponderAssignment.assigned_at >= start_of_day,
            ResponderAssignment.assigned_at < start_of_tomorrow,
        )
        .order_by(ResponderAssignment.assigned_at.desc())
    ).all()

    todays_assignments = [
        _to_assignment_item(assignment, incident)
        for assignment, incident in today_rows
    ]

    return ResponderDashboardResponse(
        active_responses=active_responses,
        active_count=active_count,
        completed_count=completed_count,
        todays_assignments=todays_assignments,
    )


def complete_responder_assignment(
    session: Session,
    incident_id: int,
    assignment_id: int,
    responder: User,
    response_outcome: ResponderResponseOutcome,
    response_note: str,
    evidence_file: UploadFile,
):
    incident = _get_incident_or_404(session, incident_id)
    profile = _get_responder_profile(session, responder)

    assignment = session.exec(
        select(ResponderAssignment).where(
            ResponderAssignment.id == assignment_id,
            ResponderAssignment.incident_id == incident_id,
            ResponderAssignment.responder_id == profile.id,
        )
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found.",
        )

    if assignment.status != ResponderAssignmentStatus.on_scene:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A response can only be completed while the assignment is on scene.",
        )

    if not response_note.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Response note is required.",
        )

    if not evidence_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one proof of response photo is required.",
        )

    assignment.response_outcome = response_outcome
    assignment.response_note = response_note.strip()
    assignment.status = ResponderAssignmentStatus.complete
    assignment.completed_at = datetime.utcnow()

    evidence = []

    # for file in evidence_files:
    storage_key = upload_response_evidence_to_s3(
        evidence_file,
        assignment.id,
    )

    item = ResponderCompletionEvidence(
        assignment_id=assignment.id,
        uploaded_by=responder.id,
        url=storage_key,
    )

    session.add(item)
    evidence.append(item)

    # Free responder if they have no other active assignments.
    other_active = session.exec(
        select(ResponderAssignment).where(
            ResponderAssignment.responder_id == profile.id,
            ResponderAssignment.id != assignment.id,
            ResponderAssignment.status.in_(_ACTIVE_STATUSES),
        )
    ).first()

    if not other_active:
        profile.availability_status = ResponderAvailabilityStatus.available
        profile.updated_at = datetime.utcnow()

    session.add(assignment)
    session.add(profile)

    session.add(
        IncidentUpdate(
            incident_id=incident_id,
            actor_id=responder.id,
            note=(
                f"{responder.full_name} completed the response. "
                f"Outcome: {response_outcome.value.replace('_', ' ')}."
            ),
            old_status=incident.status,
            new_status=incident.status,
        )
    )

    session.commit()
    session.refresh(assignment)

    for item in evidence:
        session.refresh(item)

    assignment_read = _to_read(
        assignment,
        profile,
        responder,
    )

    evidence_read = [
        ResponderCompletionEvidenceRead(
            id=item.id,
            assignment_id=item.assignment_id,
            uploaded_by=item.uploaded_by,
            url=generate_presigned_url(item.url),
            uploaded_at=item.uploaded_at,
        )
        for item in evidence
    ]

    return ResponderCompletionResponse(
        assignment=assignment_read,
        evidence=evidence_read,
    )
