from datetime import datetime

from pydantic import BaseModel

from enums.incident import EmergencyType, IncidentSeverity, IncidentStatus
from enums.responder import ResponderAssignmentStatus
from schemas.incident import IncidentMediaRead


class ResponderAssignmentListItem(BaseModel):
    assignment_id: int
    incident_id: int
    reference_code: str

    emergency_type: EmergencyType
    emergency_type_other: str | None
    location: str
    severity: IncidentSeverity
    incident_status: IncidentStatus

    assignment_status: ResponderAssignmentStatus
    assigned_at: datetime
    completed_at: datetime | None


class ResponderAssignmentsResponse(BaseModel):
    assignments: list[ResponderAssignmentListItem]

    active_count: int
    completed_count: int
    total: int

    page: int
    limit: int
    total_pages: int


class ResponderTeamMember(BaseModel):
    responder_id: int
    full_name: str
    position: str | None
    employee_id: str | None
    assignment_status: ResponderAssignmentStatus


class ResponderAssignmentDetails(BaseModel):
    assignment_id: int

    incident_id: int
    reference_code: str

    emergency_type: EmergencyType
    emergency_type_other: str | None
    description: str
    location: str
    severity: IncidentSeverity
    incident_status: IncidentStatus
    occurred_at: datetime
    reported_at: datetime

    assignment_status: ResponderAssignmentStatus
    assigned_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    media: list[IncidentMediaRead]
    response_team: list[ResponderTeamMember]


class ResponderDashboardResponse(BaseModel):
    active_responses: list[ResponderAssignmentListItem]

    active_count: int
    completed_count: int

    todays_assignments: list[ResponderAssignmentListItem]
