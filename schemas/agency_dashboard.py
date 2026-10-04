from datetime import datetime

from pydantic import BaseModel

from enums.incident import (
    EmergencyType,
    IncidentSeverity,
    IncidentAgencyStatus,
)


class IncidentOverview(BaseModel):
    new: int
    verified: int
    assigned: int
    dispatched: int
    in_progress: int
    resolved: int


class IncomingIncident(BaseModel):
    id: int
    reference_code: str
    emergency_type: EmergencyType
    severity: IncidentSeverity
    description: str
    location: str
    status: IncidentAgencyStatus
    occurred_at: datetime


class IncomingIncidentsResponse(BaseModel):
    data: list[IncomingIncident]
    total: int


class AgencyDashboardResponse(BaseModel):
    incident_overview: IncidentOverview
    incoming_incidents: IncomingIncidentsResponse
