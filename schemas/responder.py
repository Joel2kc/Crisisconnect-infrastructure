from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from enums.responder import (
    ResponderAvailabilityStatus,
    ResponderAssignmentStatus,
)
from enums.user import UserRole
from schemas.responder_assignment import ResponderAssignmentRead


class ResponderCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    position: str | None = None
    employee_id: str | None = None
    skill_ids: list[int] = Field(default_factory=list)


class ResponderUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    position: str | None = None
    employee_id: str | None = None
    availability_status: ResponderAvailabilityStatus | None = None
    skill_ids: list[int] | None = None


class ResponderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    full_name: str
    email: EmailStr
    phone: str | None
    position: str | None
    employee_id: str | None
    availability_status: ResponderAvailabilityStatus
    is_active: bool
    created_at: datetime


class ResponderCreationResult(BaseModel):
    responder: ResponderRead
    temporary_password: str


class ResponderAssignmentCreate(BaseModel):
    responder_id: int


class ResponderAssignmentStatusUpdate(BaseModel):
    status: ResponderAssignmentStatus

class ResponderListResponse(BaseModel):
    responders: list[ResponderRead]
    total: int
    page: int
    limit: int
    total_pages: int

class ResponderCompletionEvidenceRead(BaseModel):
    id: int
    assignment_id: int
    uploaded_by: int
    url: str
    uploaded_at: datetime

class ResponderCompletionResponse(BaseModel):
    assignment: ResponderAssignmentRead
    evidence: list[ResponderCompletionEvidenceRead]
