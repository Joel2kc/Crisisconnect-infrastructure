import uuid
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Depends, Request, File, Form, HTTPException, UploadFile

from core.dependencies import CurrentUser, CurrentUserOptional, require_role
from core.session_dependency import sessionDep
from db.models.user_model import User
from enums.user import UserRole
from rate_limiter.rate_limiter import limiter
from schemas.incident import (
    IncidentCreateRequest,
    IncidentDetailResponse,
    IncidentListItem,
    IncidentMediaRead,
    IncidentAgencyStatusUpdateRequest,
    IncidentRejectRequest,
)
from services.incident_service import (
    create_incident,
    get_incident_detail,
    track_incident,
    add_incident_media,
    update_incident_agency_status,
    reject_incident,
    list_incidents,
)
from services.ai_service import analyse_in_background
from services.incident_email_service import (
    collect_incident_recipients,
    incident_context,
    send_incident_routed_email,
)
from services.file_storage_service import upload_incident_media_to_s3
from enums.incident import IncidentStatus, IncidentSeverity, EmergencyType
from pydantic import ValidationError

incident_router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["Incidents"],
)


@incident_router.get("", response_model=list[IncidentListItem])
def list_all_incidents(
    session: sessionDep,
    current_user: CurrentUser,
    status_filter: IncidentStatus | None = None,
    severity_filter: IncidentSeverity | None = None,
    emergency_type_filter: EmergencyType | None = None,
):
    """
    For dashboard listing. Agency staff see only incidents routed to their
    own agency; Crisis Connect Admin and government officials see all
    (government view is read-only monitoring, no write endpoints are
    exposed to that role).
    """
    return list_incidents(
        session, current_user, status_filter, severity_filter, emergency_type_filter
    )


@incident_router.post("", response_model=IncidentDetailResponse, status_code=201)
@limiter.limit("10/hour")
def report_incident(
    request: Request,
    session: sessionDep,
    background_tasks: BackgroundTasks,
    reporter: CurrentUserOptional,
    emergency_type: EmergencyType = Form(...),
    emergency_type_other: str | None = Form(None),
    description: str = Form(...),
    location: str = Form(...),
    latitude: float | None = Form(
        None, description="Incident latitude. Enables automatic arrival detection."
    ),
    longitude: float | None = Form(
        None, description="Incident longitude. Enables automatic arrival detection."
    ),
    severity: IncidentSeverity = Form(...),
    occurred_at: datetime = Form(...),
    # files: list[UploadFile] | None = File(default=None),
    files: UploadFile | None = File(default=None),
):
    """
    Reports an emergency - a single multipart request carrying both the
    report details and any attached photos/videos, so the whole thing
    succeeds or fails together. 
    Works with or without an account. Anonymous citizens can report; logged-in users
    get reporter_id attached automatically from their token.
    """
    try:
        payload = IncidentCreateRequest(
            emergency_type=emergency_type,
            emergency_type_other=emergency_type_other,
            description=description,
            location=location,
            latitude=latitude,
            longitude=longitude,
            severity=severity,
            occurred_at=occurred_at,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": err["loc"], "msg": err["msg"]} for err in e.errors()],
        )
    result = create_incident(session, payload, reporter, files)

    # AI triage runs in the background so a 2-5 second Gemini call never
    # delays a citizen reporting an emergency. The incident is committed
    # by this point, and analyse_in_background swallows every failure -
    # a report is a valid report with or without an analysis attached.
    background_tasks.add_task(analyse_in_background, result.incident.id)

    # Tell the agencies it was routed to. Recipients are resolved now,
    # while the session is still open; the sends themselves are queued so
    # a slow or unreachable SMTP server never delays the citizen's
    # response. Until this existed, IncidentAgency.status said 'notified'
    # while nothing had actually been sent to anyone.
    context = incident_context(result.incident)
    for email, agency_name in collect_incident_recipients(session, result.incident.id):
        background_tasks.add_task(
            send_incident_routed_email, email, agency_name, context
        )

    return result


@incident_router.get("/track/{reference_code}", response_model=IncidentDetailResponse)
@limiter.limit("20/hour")
def track(request: Request, reference_code: str, session: sessionDep):
    """
    Anonymous status lookup by reference code - no auth required.
    """
    return track_incident(session, reference_code)


@incident_router.get("/{incident_id}", response_model=IncidentDetailResponse)
def get_incident(incident_id: int, session: sessionDep, current_user: CurrentUser):
    return get_incident_detail(session, incident_id, current_user)


@incident_router.post("/{incident_id}/media", response_model=IncidentMediaRead, status_code=201)
@limiter.limit("10/hour")
def upload_incident_media(
    request: Request,
    incident_id: int,
    session: sessionDep,
    reporter: CurrentUserOptional,
    file: UploadFile = File(...),
):
    """
    Attaches ADDITIONAL media to an incident that already exists (e.g. a
    witness sends more photos later)
    """

    file_url = upload_incident_media_to_s3(file, incident_id)
    return add_incident_media(session, incident_id, file_url, reporter)


@incident_router.patch(
    "/{incident_id}/agencies/{agency_id}/status", response_model=IncidentDetailResponse
)
def update_agency_status(
    incident_id: int,
    agency_id: int,
    payload: IncidentAgencyStatusUpdateRequest,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Updates the calling agency's own status on this incident. Restricted
    to members of that agency (or Crisis Connect Admin) - enforced in
    the service layer since it depends on matching agency_id, not just role.
    """
    return update_incident_agency_status(session, incident_id, agency_id, payload, current_user)


RejectorUser = Annotated[
    User,
    Depends(
        require_role(
            UserRole.crisis_connect_admin,
            UserRole.agency_admin,
            UserRole.agency_dispatcher,
        )
    ),
]


@incident_router.post("/{incident_id}/reject", response_model=IncidentDetailResponse)
def reject(
    incident_id: int,
    payload: IncidentRejectRequest,
    session: sessionDep,
    current_user: RejectorUser,
):
    return reject_incident(session, incident_id, payload.reason, current_user)
