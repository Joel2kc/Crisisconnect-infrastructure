from datetime import datetime

from pydantic import BaseModel, Field

from enums.location import AssigneeKind


class LocationPingCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    recorded_at: datetime | None = None


class LocationPingRead(BaseModel):
    id: int
    incident_id: int
    assignment_id: int
    assignee_kind: AssigneeKind
    latitude: float
    longitude: float
    accuracy_m: float | None
    distance_m: float | None
    recorded_at: datetime
    assignment_status: str | None = None
    status_changed: bool = False
    tracking_active: bool = True
