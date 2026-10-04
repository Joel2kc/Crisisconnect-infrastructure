from datetime import datetime

from sqlmodel import SQLModel, Field

from enums.incident import (
    EmergencyType,
    IncidentSeverity,
    IncidentStatus,
    IncidentAgencyRole,
    IncidentAgencyStatus,
)


class Incident(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    # lookup code for citizens without an account
    reference_code: str = Field(unique=True, index=True)

    # Nullable - citizens can report without an account
    reporter_id: int | None = Field(default=None, foreign_key="user.id")

    emergency_type: EmergencyType
    # Only populated when emergency_type == others (free-text "Tell us
    # your emergency" field on that path in the design)
    emergency_type_other: str | None = None

    description: str
    location: str
    # Where the incident actually is. Nullable because every incident
    # reported before this existed has none, and because citizens decline
    # location permission routinely - the geofence degrades to manual
    # status updates rather than blocking the report.
    latitude: float | None = None
    longitude: float | None = None
    severity: IncidentSeverity
    status: IncidentStatus = Field(default=IncidentStatus.reported)
    occurred_at: datetime

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IncidentMedia(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    incident_id: int = Field(foreign_key="incident.id")
    uploaded_by: int | None = Field(default=None, foreign_key="user.id")
    url: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class IncidentAgency(SQLModel, table=True):
    """
    Links an incident to every agency routed to it (matched on
    emergency_type only for now). Multiple agencies can be
    linked to one incident; each tracks its own status independently.
    """
    id: int | None = Field(default=None, primary_key=True)
    incident_id: int = Field(foreign_key="incident.id")
    agency_id: int = Field(foreign_key="agency.id")
    role: IncidentAgencyRole = Field(default=IncidentAgencyRole.primary)
    status: IncidentAgencyStatus = Field(default=IncidentAgencyStatus.notified)
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class IncidentUpdate(SQLModel, table=True):
    """
    Lightweight status/timeline log
    """
    id: int | None = Field(default=None, primary_key=True)
    incident_id: int = Field(foreign_key="incident.id")
    actor_id: int | None = Field(default=None, foreign_key="user.id")

    note: str | None = None
    old_status: IncidentStatus | None = None
    new_status: IncidentStatus

    created_at: datetime = Field(default_factory=datetime.utcnow)
