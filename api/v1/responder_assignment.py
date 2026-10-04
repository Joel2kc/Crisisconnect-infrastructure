from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    UploadFile,
    File,
)
from typing import Annotated

from core.dependencies import CurrentUser, require_role
from core.session_dependency import sessionDep
from db.models.ai_model import IncidentAnalysis
from schemas.responder import (
    ResponderAssignmentCreate,
    ResponderAssignmentStatusUpdate,
    ResponderCompletionResponse,
)
from schemas.responder_assignment import ResponderAssignmentRead
from services.incident_email_service import (
    incident_context,
    send_responder_assigned_email,
)
from services.responder_assignment_service import (
    assign_responder,
    cancel_assignment,
    list_assignments,
    update_assignment_status,
)
from sqlmodel import select
from db.models.user_model import User
from core.dependencies import require_role
from enums.user import UserRole
from services.responder_dashboard_service import complete_responder_assignment
from enums.responder import ResponderResponseOutcome

responder_assignment_router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["Responder Assignments"],
)

ResponderUser = Annotated[
    User,
    Depends(require_role(UserRole.responder)),
]


@responder_assignment_router.post(
    "/{incident_id}/responders/{assignment_id}/complete",
    response_model=ResponderCompletionResponse,
)
def complete_response(
    incident_id: int,
    assignment_id: int,
    session: sessionDep,
    current_user: ResponderUser,
    response_outcome: ResponderResponseOutcome = Form(...),
    response_note: str = Form(...),
    evidence_file: UploadFile = File(...),
):
    return complete_responder_assignment(
        session=session,
        incident_id=incident_id,
        assignment_id=assignment_id,
        responder=current_user,
        response_outcome=response_outcome,
        response_note=response_note,
        evidence_file=evidence_file,
    )


@responder_assignment_router.post(
    "/{incident_id}/responders",
    response_model=ResponderAssignmentRead,
    status_code=201,
)
def dispatch_responder(
    incident_id: int,
    payload: ResponderAssignmentCreate,
    session: sessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    """
    Dispatches one of your agency's responders to this incident.

    Restricted to agency admins and dispatchers whose agency the incident
    was actually routed to - checked against IncidentAgency, not role
    alone. The responder must belong to that same agency.

    Records who dispatched them, marks the responder 'assigned', writes
    an entry to the incident timeline, and emails the responder with the
    incident details and any hazards the analysis flagged.
    """
    assignment, incident = assign_responder(
        session, incident_id, payload.responder_id, current_user
    )

    analysis = session.exec(
        select(IncidentAnalysis).where(IncidentAnalysis.incident_id == incident_id)
    ).first()
    hazards = (analysis.hazards or []) if analysis else []

    background_tasks.add_task(
        send_responder_assigned_email,
        assignment.email,
        assignment.full_name,
        hazards,
        incident_context(incident),
    )
    return assignment


@responder_assignment_router.get(
    "/{incident_id}/responders", response_model=list[ResponderAssignmentRead]
)
def read_assignments(
    incident_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    """Every responder dispatched to this incident, oldest first."""
    return list_assignments(session, incident_id, current_user)


# No one is allow to manually update responder status, only GPS does it,
# Responder completes the process through the complete_response endpoint
@responder_assignment_router.patch(
    "/{incident_id}/responders/{assignment_id}",
    response_model=ResponderAssignmentRead,
)
def update_status(
    incident_id: int,
    assignment_id: int,
    payload: ResponderAssignmentStatusUpdate,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Updates the operational status of a responder assignment.

    The assignment can be moved between operational states such as
    assigned, en_route, and on_scene. Completion is handled through the
    dedicated completion endpoint because it requires an outcome, response
    note, and proof of response.

    Steps may be skipped - real incidents do.
    """
    return update_assignment_status(
        session, incident_id, assignment_id, payload.status, current_user
    )


@responder_assignment_router.delete(
    "/{incident_id}/responders/{assignment_id}", status_code=204
)
def stand_down(
    incident_id: int,
    assignment_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Cancels a dispatch that has not started yet.

    Only while the status is still 'assigned'. Once a responder is en
    route the assignment is part of the incident's history and is closed
    with 'complete' rather than deleted.
    """
    cancel_assignment(session, incident_id, assignment_id, current_user)
