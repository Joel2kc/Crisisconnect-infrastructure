from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from enums.incident import EmergencyType, IncidentSeverity
from enums.volunteer_assignment import VolunteerAssignmentStatus


class VolunteerInviteRequest(BaseModel):
    volunteer_id: int
    # Optional instructions from the agency: where to meet, what to bring.
    note: str | None = Field(default=None, max_length=1000)


class VolunteerResponseRequest(BaseModel):
    """What a volunteer sends back from their dashboard."""

    accept: bool
    response_note: str | None = Field(default=None, max_length=1000)


class VolunteerAssignmentRead(BaseModel):
    """Agency-facing view: who was invited and what they said."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    agency_id: int

    volunteer_id: int
    user_id: int
    full_name: str
    email: str
    phone: str | None

    status: VolunteerAssignmentStatus
    matched_skills: list[str]
    note: str | None
    response_note: str | None

    invited_by: int
    invited_at: datetime
    responded_at: datetime | None
    completed_at: datetime | None


class VolunteerAssignmentDashboardItem(BaseModel):
    """
    Volunteer-facing view: one card on the volunteer's dashboard.

    Carries the incident details a volunteer needs in order to answer -
    including hazards, because nobody should accept without knowing what
    is at the scene. It deliberately does not expose the reporter, the
    other volunteers invited, or anything else about the incident.
    """

    id: int
    incident_id: int
    status: VolunteerAssignmentStatus

    agency_name: str
    reference_code: str
    emergency_type: EmergencyType
    severity: IncidentSeverity
    location: str
    description: str
    occurred_at: datetime

    # From the AI analysis when one exists. Empty list when it does not.
    hazards: list[str]
    matched_skills: list[str]
    note: str | None

    invited_at: datetime
    responded_at: datetime | None
