from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, model_validator, Field

from enums.incident import (
    EmergencyType,
    IncidentSeverity,
    IncidentStatus,
    IncidentAgencyRole,
    IncidentAgencyStatus,
)


class IncidentCreateRequest(BaseModel):
    emergency_type: EmergencyType
    emergency_type_other: str | None = None
    description: str
    location: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    severity: IncidentSeverity
    occurred_at: datetime

    @model_validator(mode="after")
    def others_requires_detail(self):
        if self.emergency_type == EmergencyType.others and not (
            self.emergency_type_other and self.emergency_type_other.strip()
        ):
            raise ValueError(
                "emergency_type_other is required when emergency_type is 'others'."
            )
        return self

    @model_validator(mode="after")
    def occurred_at_not_in_future(self):
        occurred_at = self.occurred_at

        # Convert timezone-aware datetime to naive UTC
        if occurred_at.tzinfo is not None:
            occurred_at = occurred_at.astimezone(timezone.utc).replace(tzinfo=None)
        
        if occurred_at > datetime.utcnow():
            raise ValueError("occurred_at cannot be in the future.")
        
        self.occurred_at = occurred_at
        return self


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_code: str
    reporter_id: int | None
    emergency_type: EmergencyType
    emergency_type_other: str | None
    description: str
    location: str
    latitude: float | None
    longitude: float | None
    severity: IncidentSeverity
    status: IncidentStatus
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class IncidentMediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    uploaded_by: int | None
    url: str
    uploaded_at: datetime


class IncidentAgencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    agency_id: int
    role: IncidentAgencyRole
    status: IncidentAgencyStatus
    assigned_at: datetime


class IncidentUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    actor_id: int | None
    note: str | None
    old_status: IncidentStatus | None
    new_status: IncidentStatus
    created_at: datetime


class IncidentDetailResponse(BaseModel):
    incident: IncidentRead
    agencies: list[IncidentAgencyRead]
    media: list[IncidentMediaRead]
    updates: list[IncidentUpdateRead]


class IncidentAgencyStatusUpdateRequest(BaseModel):
    status: IncidentAgencyStatus
    note: str | None = None


class IncidentRejectRequest(BaseModel):
    reason: str


class IncidentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
 
    id: int
    reference_code: str
    emergency_type: EmergencyType
    emergency_type_other: str | None
    severity: IncidentSeverity
    status: IncidentStatus
    location: str
    latitude: float | None
    longitude: float | None
    occurred_at: datetime
    created_at: datetime
 
    # Only populated for agency-scoped requests - this agency's own
    # status on the incident, distinct from the incident-wide status
    # above (status: IncidentStatus).
    your_agency_status: IncidentAgencyStatus | None = None
