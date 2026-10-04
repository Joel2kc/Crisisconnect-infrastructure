from datetime import datetime

from pydantic import BaseModel, ConfigDict

from enums.agency import AgencyType
from enums.ai import AnalysisStatus
from enums.incident import EmergencyType, IncidentSeverity
from enums.resource import FuelLevel, ResourceCategory, ResourceCondition, ResourceType
from enums.responder import ResponderAvailabilityStatus
from enums.volunteer import AvailabilityStatus


class IncidentAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_id: int
    status: AnalysisStatus

    summary: str | None
    suggested_emergency_type: EmergencyType | None
    suggested_severity: IncidentSeverity | None
    key_facts: list[str]
    hazards: list[str]
    suggested_skills: list[str]
    recommended_agency_types: list[str]
    required_resources: list[str]
    confidence: float | None
    needs_human_review: bool

    # Badge these in the dashboard - they are the actionable part.
    type_disagreement: bool
    severity_escalation: bool

    # Populated when status is 'failed'. Render it as "analysis
    # unavailable", never as an empty analysis panel.
    error: str | None

    latency_ms: int | None
    completed_at: datetime | None


class VolunteerMatch(BaseModel):
    """
    One volunteer whose registered skills overlap the analysis.

    A suggestion, never an assignment. Nothing in the schema records a
    volunteer against an incident, so acting on this is a phone call the
    dispatcher makes and logs elsewhere.

    Contact details are included because the only useful next step is
    reaching the person, and the endpoint is restricted to coordinating
    roles. Drop the email and phone fields if volunteer contact data
    should stay inside the volunteer module.
    """

    volunteer_id: int
    user_id: int
    full_name: str
    email: str
    phone: str | None

    # Which of the analysis's skills this person holds, and how many -
    # the ranking is by this count, so showing it makes the order legible.
    matched_skills: list[str]
    matched_skill_count: int

    availability_status: list[AvailabilityStatus]
    # Free text the volunteer wrote at registration. Unverified.
    certifications: str | None

    # Place names shared between the volunteer's address and the incident
    # location, both of which are free text. A match means they wrote a
    # place name the incident also mentions - useful for ranking, and
    # never used to exclude anyone: an empty list can just as easily mean
    # they phrased their address differently as that they are far away.
    address: str | None = None
    matched_location_terms: list[str] = []
    location_match: bool = False


class VolunteerSuggestionResponse(BaseModel):
    incident_id: int

    # What the model asked for, what existed in the Skill table, and what
    # did not. unmatched_skills is the useful diagnostic: it shows exactly
    # where Gemini's vocabulary and the seeded skills diverge, which is
    # how you learn what to seed next.
    suggested_skills: list[str]
    resolved_skills: list[str]
    unmatched_skills: list[str]

    matches: list[VolunteerMatch]

    # Populated only when matches is empty, explaining why. Lets the
    # dashboard say something specific instead of showing a blank panel.
    reason: str | None = None


# --------------------------------------------------------------------
# The unified recommendation panel: analyse -> route -> who and what to
# send. Every field below is a suggestion; none of it is an assignment.
# --------------------------------------------------------------------


class RoutingRecommendation(BaseModel):
    """
    Whether the incident reached the right agencies.

    reaches_no_agency is the case that matters most. Routing matches
    AgencyCoverage on emergency_type, and 'others' matches no coverage
    row at all, so an incident filed that way is notified to nobody.
    """

    reported_emergency_type: EmergencyType
    suggested_emergency_type: EmergencyType | None
    type_disagreement: bool
    severity_escalation: bool
    routed_agency_ids: list[int]
    reaches_no_agency: bool


class AgencySuggestion(BaseModel):
    agency_id: int
    name: str
    type: AgencyType
    region: str | None
    # Why this agency is being suggested, in words a dispatcher can judge:
    # either it covers the type the AI read, or the AI named its type.
    reason: str


class ResponderMatch(BaseModel):
    responder_id: int
    user_id: int
    full_name: str
    email: str
    phone: str | None
    position: str | None
    employee_id: str | None
    availability_status: ResponderAvailabilityStatus
    matched_skills: list[str]
    matched_skill_count: int


class ResourceMatch(BaseModel):
    resource_id: int
    name: str
    asset_number: str | None
    category: ResourceCategory
    condition: ResourceCondition
    quantity: int
    location: str
    fuel_level: FuelLevel | None
    # Show this. Inventory is only as good as its last update, and a row
    # nobody has touched in weeks should read as unknown, not available.
    last_updated: datetime


class ResourceRequirement(BaseModel):
    resource_type: ResourceType
    available: list[ResourceMatch]
    available_count: int
    # True when the agency holds nothing of this type. The gap is the
    # useful half - it is what sends a dispatcher to another agency.
    missing: bool


class IncidentRecommendations(BaseModel):
    incident_id: int
    # Whose responders and resources these are. None when the incident
    # has reached no agency and the caller belongs to none.
    agency_id: int | None
    analysis_status: AnalysisStatus

    summary: str | None = None
    hazards: list[str] = []

    routing: RoutingRecommendation
    suggested_agencies: list[AgencySuggestion] = []

    responders: list[ResponderMatch] = []
    volunteers: list[VolunteerMatch] = []
    resources: list[ResourceRequirement] = []

    # Skill vocabulary diagnostics, shared by responder and volunteer
    # matching. unmatched_skills shows where Gemini's names and the Skill
    # table diverge, which is how you learn what to seed.
    suggested_skills: list[str] = []
    resolved_skills: list[str] = []
    unmatched_skills: list[str] = []

    reason: str | None = None
