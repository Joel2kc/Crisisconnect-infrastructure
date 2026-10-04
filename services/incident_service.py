from datetime import datetime

from fastapi import HTTPException, status, UploadFile
from sqlmodel import Session, select

from core.reference_code import generate_reference_code
from db.models.agency_model import AgencyCoverage
from db.models.incident_model import Incident, IncidentAgency, IncidentMedia, IncidentUpdate
from db.models.user_model import User
from enums.incident import IncidentAgencyRole, IncidentAgencyStatus, IncidentStatus
from schemas.incident import (
    IncidentCreateRequest,
    IncidentDetailResponse,
    IncidentAgencyStatusUpdateRequest,
    IncidentRead,
    IncidentAgencyRead,
    IncidentMediaRead,
    IncidentUpdateRead,
    IncidentListItem,
)
from services.file_storage_service import (
    generate_presigned_url,
    upload_incident_media_to_s3,
)


def create_incident(
    session: Session,
    payload: IncidentCreateRequest,
    reporter: User | None,
    files: UploadFile | None = None,
) -> IncidentDetailResponse:
    """
    Creates an incident and routes it to every agency whose active
    AgencyCoverage matches the reported emergency_type for now, and uploads
    any attached photos/videos to S3 - all as one database transaction.
    The first matching agency is marked primary; the rest marked supporting.
    reporter is None for anonymous citizen reports.

    We flush (not commit) to get incident.id first, since
    the S3 key needs it, then upload to S3, and only commit once every
    upload has succeeded. If any upload fails, the incident row is
    never committed at all.
    """
    reference_code = generate_reference_code(session, Incident, payload.emergency_type)

    incident = Incident(
        reference_code=reference_code,
        reporter_id=reporter.id if reporter else None,
        emergency_type=payload.emergency_type,
        emergency_type_other=payload.emergency_type_other,
        description=payload.description,
        location=payload.location,
        latitude=payload.latitude,
        longitude=payload.longitude,
        severity=payload.severity,
        occurred_at=payload.occurred_at,
    )
    session.add(incident)
    session.flush()

    coverage_matches = session.exec(
        select(AgencyCoverage).where(
            AgencyCoverage.emergency_type == payload.emergency_type,
            AgencyCoverage.active == True,
        )
    ).all()

    linked_agencies = []
    for i, coverage in enumerate(coverage_matches):
        incident_agency = IncidentAgency(
            incident_id=incident.id,
            agency_id=coverage.agency_id,
            role=IncidentAgencyRole.primary if i == 0 else IncidentAgencyRole.supporting,
            status=IncidentAgencyStatus.notified,
        )
        session.add(incident_agency)
        linked_agencies.append(incident_agency)

    initial_update = IncidentUpdate(
        incident_id=incident.id,
        actor_id=None,
        note=(
            f"Report submitted and routed to {len(linked_agencies)} agenc"
            f"{'y' if len(linked_agencies) == 1 else 'ies'}."
            if linked_agencies
            else "Report submitted - no agency currently covers this emergency type."
        ),
        old_status=None,
        new_status=IncidentStatus.reported,
    )
    session.add(initial_update)

    # Every attached file is uploaded to S3 now that incident.id exists. If
    # any upload raises, we return without ever calling commit() -
    # nothing (incident, agencies, update log) ends up persisted.
    media_objects = []
    # for file in (files or []): #TODO: Make sure multiple files can be sent
    if files:
        url = upload_incident_media_to_s3(files, incident.id)
        media = IncidentMedia(
            incident_id=incident.id,
            uploaded_by=reporter.id if reporter else None,
            url=url,
        )
        session.add(media)
        media_objects.append(media)

    session.commit()
    session.refresh(incident)
    for incident_agency in linked_agencies:
        session.refresh(incident_agency)
    session.refresh(initial_update)
    for media in media_objects:
        session.refresh(media)

    return IncidentDetailResponse(
        incident=IncidentRead.model_validate(incident),
        agencies=[IncidentAgencyRead.model_validate(ia) for ia in linked_agencies],
        media=[
            IncidentMediaRead(
                id=m.id,
                incident_id=m.incident_id,
                uploaded_by=m.uploaded_by,
                url=generate_presigned_url(m.url),
                uploaded_at=m.uploaded_at,
            )
            for m in media_objects
        ],
        updates=[IncidentUpdateRead.model_validate(initial_update)],
    )


def get_incident_detail(session: Session, incident_id: int, current_user: User) -> IncidentDetailResponse:
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    _authorize_incident_view(session, incident, current_user)

    return _build_detail_response(session, incident)


def track_incident(session: Session, reference_code: str) -> IncidentDetailResponse:
    incident = session.exec(
        select(Incident).where(Incident.reference_code == reference_code)
    ).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    return _build_detail_response(session, incident)


def _build_detail_response(session: Session, incident: Incident) -> IncidentDetailResponse:
    agencies = session.exec(
        select(IncidentAgency).where(IncidentAgency.incident_id == incident.id)
    ).all()

    media = session.exec(
        select(IncidentMedia).where(IncidentMedia.incident_id == incident.id)
    ).all()

    updates = session.exec(
        select(IncidentUpdate)
        .where(IncidentUpdate.incident_id == incident.id)
        .order_by(IncidentUpdate.created_at)
    ).all()

    return IncidentDetailResponse(
        incident=IncidentRead.model_validate(incident),
        agencies=[IncidentAgencyRead.model_validate(agency) for agency in agencies],
        media=[
            IncidentMediaRead(
                id=med.id,
                incident_id=med.incident_id,
                uploaded_by=med.uploaded_by,
                url=generate_presigned_url(med.url),
                uploaded_at=med.uploaded_at,
            )
            for med in media
        ],
        updates=[IncidentUpdateRead.model_validate(update) for update in updates],
    )


def add_incident_media(
    session: Session, incident_id: int, url: str, uploaded_by: User | None
) -> IncidentMediaRead:
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    media = IncidentMedia(
        incident_id=incident_id,
        uploaded_by=uploaded_by.id if uploaded_by else None,
        url=url,
    )
    session.add(media)
    session.commit()
    session.refresh(media)
    return IncidentMediaRead.model_validate(media)


# Statuses that roll up from the PRIMARY agency's status alone.
# 'resolved' is deliberately excluded — see _maybe_resolve_incident.
_PRIMARY_DRIVEN_ROLLUP = {
    IncidentAgencyStatus.verified: IncidentStatus.verified,
    IncidentAgencyStatus.dispatched: IncidentStatus.dispatched,
    IncidentAgencyStatus.responding: IncidentStatus.in_progress,
}


def update_incident_agency_status(
    session: Session,
    incident_id: int,
    agency_id: int,
    payload: IncidentAgencyStatusUpdateRequest,
    actor: User,
) -> IncidentDetailResponse:
    """
    Updates one agency's status on an incident, then rolls that up to
    Incident.status:
      - the PRIMARY agency's status drives verified/dispatched/in_progress
      - 'resolved' only rolls up once EVERY linked agency has resolved
        (a supporting agency finishing doesn't end the incident on its own)
    """
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    incident_agency = session.exec(
        select(IncidentAgency).where(
            IncidentAgency.incident_id == incident_id,
            IncidentAgency.agency_id == agency_id,
        )
    ).first()

    if not incident_agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This agency is not linked to this incident.",
        )

    # Authorization: caller must belong to this specific agency, or be a
    # Crisis Connect Admin.
    if actor.role.value != "crisis_connect_admin" and actor.agency_id != agency_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update incidents for your own agency.",
        )

    incident_agency.status = payload.status
    session.add(incident_agency)

    old_incident_status = incident.status

    if payload.status == IncidentAgencyStatus.resolved:
        _maybe_resolve_incident(session, incident)
    elif incident_agency.role == IncidentAgencyRole.primary:
        new_status = _PRIMARY_DRIVEN_ROLLUP.get(payload.status)
        if new_status:
            incident.status = new_status
            incident.updated_at = datetime.utcnow()
            session.add(incident)

    if incident.status != old_incident_status:
        update_log = IncidentUpdate(
            incident_id=incident.id,
            actor_id=actor.id,
            note=payload.note,
            old_status=old_incident_status,
            new_status=incident.status,
        )
        session.add(update_log)

    session.commit()
    session.refresh(incident)

    return _build_detail_response(session, incident)


def _maybe_resolve_incident(session: Session, incident: Incident) -> None:
    """Changes the status of an incident to resolved when all agencies associated
    with an incident have their IncidentAgencyStatus as resolved.
    """
    all_agencies = session.exec(
        select(IncidentAgency).where(IncidentAgency.incident_id == incident.id)
    ).all()

    if all_agencies and all(
        a.status == IncidentAgencyStatus.resolved for a in all_agencies
    ):
        incident.status = IncidentStatus.resolved
        incident.updated_at = datetime.utcnow()
        session.add(incident)


def reject_incident(
    session: Session, incident_id: int, reason: str, actor: User
) -> IncidentDetailResponse:
    """
    Marks a report as false/duplicate/non-actionable
    """
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    if incident.status == IncidentStatus.rejected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Incident is already rejected."
        )

    old_status = incident.status
    incident.status = IncidentStatus.rejected
    incident.updated_at = datetime.utcnow()
    session.add(incident)

    update_log = IncidentUpdate(
        incident_id=incident.id,
        actor_id=actor.id,
        note=reason,
        old_status=old_status,
        new_status=IncidentStatus.rejected,
    )
    session.add(update_log)

    session.commit()
    session.refresh(incident)

    return _build_detail_response(session, incident)

_AGENCY_SCOPED_ROLES = {"agency_admin", "agency_dispatcher", "responder"}
_ALL_INCIDENTS_ROLES = {"crisis_connect_admin", "government_official"} 
 
def list_incidents(
    session: Session,
    current_user: User,
    status_filter: IncidentStatus | None = None,
    severity_filter=None,
    emergency_type_filter=None,
) -> list[IncidentListItem]:
    """
    Agency staff (agency_admin/agency_dispatcher/responder) see only
    incidents routed to their own agency, alongside their agency's own
    status on each one. Crisis Connect Admin and government officials
    see every incident (read-only monitoring for government, per PRD -
    only listing is exposed, not the status-update or
    reject actions, to that role).
    """
    role_value = current_user.role.value
 
    if role_value in _AGENCY_SCOPED_ROLES:
        if not current_user.agency_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not linked to an agency.",
            )
 
        rows = session.exec(
            select(Incident, IncidentAgency.status)
            .join(IncidentAgency, IncidentAgency.incident_id == Incident.id)
            .where(IncidentAgency.agency_id == current_user.agency_id)
        ).all()
 
        items = [
            IncidentListItem(**IncidentRead.model_validate(incident).model_dump(), your_agency_status=agency_status)
            for incident, agency_status in rows
        ]
 
    elif role_value in _ALL_INCIDENTS_ROLES:
        incidents = session.exec(select(Incident)).all()
        items = [
            IncidentListItem(**IncidentRead.model_validate(incident).model_dump(), your_agency_status=None)
            for incident in incidents
        ]
 
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view the incident list.",
        )
 
    if status_filter:
        items = [i for i in items if i.status == status_filter]
    if severity_filter:
        items = [i for i in items if i.severity == severity_filter]
    if emergency_type_filter:
        items = [i for i in items if i.emergency_type == emergency_type_filter]
 
    return items

def _authorize_incident_view(session: Session, incident: Incident, current_user: User) -> None:
    role_value = current_user.role.value

    if role_value in _ALL_INCIDENTS_ROLES:
        return

    if incident.reporter_id and incident.reporter_id == current_user.id:
        return

    if role_value in _AGENCY_SCOPED_ROLES and current_user.agency_id:
        linked = session.exec(
            select(IncidentAgency).where(
                IncidentAgency.incident_id == incident.id,
                IncidentAgency.agency_id == current_user.agency_id,
            )
        ).first()
        if linked:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to view this incident.",
    )
