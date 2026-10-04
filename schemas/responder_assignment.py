from datetime import datetime

from pydantic import BaseModel, ConfigDict

from enums.responder import (
    ResponderAssignmentStatus,
    ResponderAvailabilityStatus,
    ResponderResponseOutcome,
)


class ResponderAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int

    responder_id: int
    user_id: int
    full_name: str
    email: str
    phone: str | None
    position: str | None
    employee_id: str | None
    # The responder's current overall availability, which is not the same
    # as this assignment's status: someone can be 'complete' here and
    # still 'assigned' because of another incident.
    availability_status: ResponderAvailabilityStatus

    status: ResponderAssignmentStatus
    response_outcome: ResponderResponseOutcome | None
    response_note: str | None

    # Who dispatched them. NOT NULL in the table on purpose - every
    # dispatch names the person accountable for it.
    assigned_by: int

    assigned_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
