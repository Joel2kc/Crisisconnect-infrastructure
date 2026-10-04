from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from core.dependencies import CurrentUser, require_role
from core.session_dependency import sessionDep
from db.models.user_model import User
from enums.user import UserRole
from rate_limiter.rate_limiter import limiter
from schemas.ai import (
    IncidentAnalysisRead,
    IncidentRecommendations,
    VolunteerSuggestionResponse,
)
from services.ai_service import get_analysis, run_analysis
from services.incident_recommendation_service import recommend_for_incident
from services.volunteer_match_service import suggest_volunteers

ai_router = APIRouter(
    prefix="/api/v1/incidents",
    tags=["AI"],
)


# Running an analysis costs money and is an action, not a read, so it is
# restricted to the roles that actually coordinate a response. Government
# officials have read-only monitoring access per the PRD and are
# deliberately excluded from triggering calls.
AnalystUser = Annotated[
    User,
    Depends(
        require_role(
            UserRole.crisis_connect_admin,
            UserRole.agency_admin,
            UserRole.agency_dispatcher,
        )
    ),
]


@ai_router.post("/{incident_id}/analysis", response_model=IncidentAnalysisRead)
@limiter.limit("60/hour")
def analyse(
    request: Request,
    incident_id: int,
    session: sessionDep,
    current_user: AnalystUser,
):
    """
    Runs (or re-runs) Gemini analysis on an incident.

    Takes roughly 2-5 seconds. Agency scoping is inherited from the
    existing incident-detail rules, so staff can only analyse incidents
    routed to their own agency.

    Never raises on an AI failure - a failed analysis comes back with
    status 'failed' and an error message for the dashboard to render.
    """
    return run_analysis(session, incident_id, current_user)


@ai_router.get("/{incident_id}/analysis", response_model=IncidentAnalysisRead)
def read_analysis(
    incident_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Fetches an existing analysis without paying for a new Gemini call.

    Open to anyone already permitted to view the incident. Returns 404
    when the incident has not been analysed yet.
    """
    return get_analysis(session, incident_id, current_user)


@ai_router.get(
    "/{incident_id}/volunteer-suggestions",
    response_model=VolunteerSuggestionResponse,
)
def volunteer_suggestions(
    incident_id: int,
    session: sessionDep,
    current_user: AnalystUser,
    limit: int = Query(25, ge=1, le=100),
    include_unavailable: bool = Query(
        False,
        description=(
            "Include verified volunteers whose stated availability does not "
            "cover this incident. Ignored for high_critical incidents, where "
            "availability is never filtered."
        ),
    ),
):
    """
    Ranks registered volunteers against the incident's stored analysis.

    A database query, not an AI call - it costs nothing and is safe to
    poll. It reads suggested_skills from the existing analysis, resolves
    those names to real Skill rows, and returns the verified, available
    volunteers holding them, most matched skills first.

    Suggestion only. The schema has no volunteer-assignment table, so
    nothing here notifies anyone or records a commitment; contacting a
    volunteer stays an explicit human step.

    Restricted to coordinating roles rather than every incident viewer
    because the response carries volunteer names and contact details.

    Returns 404 if the incident has never been analysed. If it has but
    produced no usable match, the response is a normal 200 with an empty
    'matches' and a 'reason' explaining why.
    """
    return suggest_volunteers(
        session,
        incident_id,
        current_user,
        limit=limit,
        include_unavailable=include_unavailable,
    )


@ai_router.get(
    "/{incident_id}/recommendations", response_model=IncidentRecommendations
)
def recommendations(
    incident_id: int,
    session: sessionDep,
    current_user: AnalystUser,
    agency_id: int | None = Query(
        None,
        description=(
            "Whose responders and resources to show. Ignored for agency "
            "staff, who always see their own; defaults to the incident's "
            "primary agency for Crisis Connect admins."
        ),
    ),
    responder_limit: int = Query(25, ge=1, le=100),
    volunteer_limit: int = Query(25, ge=1, le=100),
    near_incident_only: bool = Query(
        False,
        description=(
            "Only volunteers whose address shares a place name with the "
            "incident location. Both are free text, so this finds shared "
            "place names, not distance - a volunteer who phrased their "
            "address differently will be filtered out even if they are "
            "nearby. Off by default for that reason."
        ),
    ),
):
    """
    The full coordination panel for one incident: where it should be
    routed, which agencies to add, which responders and volunteers to
    send, and what equipment the job needs against what the agency holds.

    A database read built on the stored analysis - no Gemini call, no
    cost, safe to poll. Returns 404 if the incident has never been
    analysed; if analysis is pending or failed, the panel comes back
    empty with a 'reason' rather than an error.

    Every section is advisory. Nothing here notifies anyone or records a
    commitment: dispatching a responder, calling a volunteer and adding
    an agency all stay explicit human actions.
    """
    return recommend_for_incident(
        session,
        incident_id,
        current_user,
        agency_id=agency_id,
        responder_limit=responder_limit,
        volunteer_limit=volunteer_limit,
        near_incident_only=near_incident_only,
    )
