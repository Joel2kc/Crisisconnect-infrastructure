from fastapi import APIRouter

from core.dependencies import CurrentUser
from core.session_dependency import sessionDep
from enums.location import AssigneeKind
from schemas.location import LocationPingCreate, LocationPingRead
from services.location_tracking_service import latest_positions, record_ping

location_router = APIRouter(prefix="/api/v1", tags=["Location Tracking"])


@location_router.post(
    "/responder-assignments/{assignment_id}/location",
    response_model=LocationPingRead,
    status_code=201,
)
def report_responder_location(
    assignment_id: int,
    payload: LocationPingCreate,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Reports a dispatched responder's current position.

    Called by the responder's own app on a timer while an assignment is
    open. Only the responder the assignment belongs to may post to it.

    Two status changes can follow, and no others: moving away from where
    they were dispatched marks them `en_route`, and arriving within the
    incident's radius marks them `on_scene`. `complete` stays manual -
    only the responder knows when the work is done.

    Always stores the ping. When the response comes back with
    `tracking_active: false` the app should stop sending: either the
    incident has no coordinates or the assignment is closed, and nothing
    further will be decided.
    """
    return record_ping(
        session,
        AssigneeKind.responder,
        assignment_id,
        current_user,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=payload.accuracy_m,
        recorded_at=payload.recorded_at,
    )


@location_router.post(
    "/volunteer-assignments/{assignment_id}/location",
    response_model=LocationPingRead,
    status_code=201,
)
def report_volunteer_location(
    assignment_id: int,
    payload: LocationPingCreate,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Reports a volunteer's current position on the way to an incident.

    Identical to the responder endpoint, with one difference that matters:
    tracking only begins once the volunteer has **accepted**. An
    invitation they have not answered, or have declined, is not tracked.

    The app must stop sending as soon as the assignment closes. This is a
    movement history of a member of the public, recorded only for a job
    they agreed to attend.
    """
    return record_ping(
        session,
        AssigneeKind.volunteer,
        assignment_id,
        current_user,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=payload.accuracy_m,
        recorded_at=payload.recorded_at,
    )


@location_router.get(
    "/incidents/{incident_id}/positions", response_model=list[LocationPingRead]
)
def incident_positions(
    incident_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Where everyone attending this incident was last seen - one position
    per responder and volunteer, newest first.

    For the dispatcher's map. Returns the latest fix only, never the
    trail.
    """
    from services.incident_service import get_incident_detail

    # Authorization is inherited: raises 404 for a missing incident and
    # 403 for an agency user the incident was not routed to, exactly as
    # the incident detail endpoint does.
    get_incident_detail(session, incident_id, current_user)
    return latest_positions(session, incident_id)
