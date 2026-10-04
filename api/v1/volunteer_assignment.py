from fastapi import APIRouter, BackgroundTasks, Query

from core.dependencies import CurrentUser
from core.session_dependency import sessionDep
from schemas.volunteer_assignment import (
    VolunteerAssignmentDashboardItem,
    VolunteerAssignmentRead,
    VolunteerInviteRequest,
    VolunteerResponseRequest,
)
from services.incident_email_service import (
    collect_agency_recipients,
    incident_context,
    send_volunteer_invited_email,
    send_volunteer_response_email,
)
from services.volunteer_assignment_service import (
    complete_volunteer_assignment,
    invite_volunteer,
    list_incident_volunteers,
    list_my_assignments,
    respond_to_assignment,
    stand_down_volunteer,
)

# Agency side: inviting from the incident view.
incident_volunteer_router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["Volunteer Assignments"],
)

# Volunteer side: their own dashboard.
volunteer_dashboard_router = APIRouter(
    prefix="/api/v1/volunteers",
    tags=["Volunteer Dashboard"],
)


@incident_volunteer_router.post(
    "/{incident_id}/volunteers",
    response_model=VolunteerAssignmentRead,
    status_code=201,
)
def invite(
    incident_id: int,
    payload: VolunteerInviteRequest,
    session: sessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    """
    Invites a volunteer to this incident.

    An invitation, not a dispatch: the volunteer decides. They are
    emailed the incident details and any hazards the analysis flagged,
    and the invitation appears on their dashboard for them to accept or
    decline.

    Restricted to agency admins and dispatchers whose agency the incident
    was routed to. The volunteer must be verified and active.
    """
    assignment, incident, agency, hazards = invite_volunteer(
        session, incident_id, payload.volunteer_id, current_user, payload.note
    )

    background_tasks.add_task(
        send_volunteer_invited_email,
        assignment.email,
        assignment.full_name,
        agency.name if agency else "A responding agency",
        hazards,
        assignment.note,
        incident_context(incident),
    )
    return assignment


@incident_volunteer_router.get(
    "/{incident_id}/volunteers", response_model=list[VolunteerAssignmentRead]
)
def list_invitations(
    incident_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Every volunteer invited to this incident and how they answered.

    This is what the suggestion list cannot tell you: who was actually
    called, who accepted, and who said no.
    """
    return list_incident_volunteers(session, incident_id, current_user)


@incident_volunteer_router.patch(
    "/{incident_id}/volunteers/{assignment_id}/stand-down",
    response_model=VolunteerAssignmentRead,
)
def stand_down(
    incident_id: int,
    assignment_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Withdraws an invitation that is still open.

    Recorded as a status rather than deleted, so a volunteer who was
    called and then told not to come sees that on their dashboard instead
    of the invitation vanishing.
    """
    return stand_down_volunteer(session, incident_id, assignment_id, current_user)


@incident_volunteer_router.patch(
    "/{incident_id}/volunteers/{assignment_id}/complete",
    response_model=VolunteerAssignmentRead,
)
def complete(
    incident_id: int,
    assignment_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    """Closes out a volunteer who accepted and has now finished."""
    return complete_volunteer_assignment(
        session, incident_id, assignment_id, current_user
    )


@volunteer_dashboard_router.get(
    "/me/assignments", response_model=list[VolunteerAssignmentDashboardItem]
)
def my_assignments(
    session: sessionDep,
    current_user: CurrentUser,
    open_only: bool = Query(
        False, description="Only invitations still awaiting a response or accepted"
    ),
):
    """
    The signed-in volunteer's own invitations, newest first.

    Scoped to the profile belonging to the token - there is no volunteer
    id to pass, so one volunteer can never read another's invitations.
    Each card carries the incident details and hazards needed to make a
    decision.
    """
    return list_my_assignments(session, current_user, open_only=open_only)


@volunteer_dashboard_router.patch(
    "/me/assignments/{assignment_id}",
    response_model=VolunteerAssignmentDashboardItem,
)
def respond(
    assignment_id: int,
    payload: VolunteerResponseRequest,
    session: sessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    """
    Accept or decline an invitation.

    Send `accept: true` or `accept: false`, optionally with a note.
    Declining is a normal answer, recorded as such - it is what tells the
    dispatcher to call someone else. Only works while the invitation is
    still awaiting a response.
    """
    item, notification = respond_to_assignment(
        session,
        assignment_id,
        current_user,
        accept=payload.accept,
        response_note=payload.response_note,
    )

    # The inviting agency hears back either way. A decline is the more
    # urgent of the two - it is what tells a dispatcher to stop waiting
    # and call somebody else.
    context = incident_context(notification["incident"])
    for email in collect_agency_recipients(session, notification["agency_id"]):
        background_tasks.add_task(
            send_volunteer_response_email,
            email,
            notification["volunteer_name"],
            notification["accepted"],
            notification["response_note"],
            notification["matched_skills"],
            notification["phone"],
            context,
        )
    return item
