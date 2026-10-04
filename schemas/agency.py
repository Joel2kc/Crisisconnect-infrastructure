from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict
from enums.agency import AgencyType, AgencyVerificationStatus
from enums.incident import EmergencyType
from schemas.user import UserRead


class AgencyApplyRequest(BaseModel):
    # Organization details
    name: str
    type: AgencyType
    registration_number: str
    org_email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    region: str | None = None

    # Account Administrator details
    admin_full_name: str
    admin_email: EmailStr
    admin_phone: str
    admin_password: str


class AgencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: AgencyType
    registration_number: str
    email: str | None
    phone: str | None
    address: str | None
    region: str | None
    verification_status: AgencyVerificationStatus
    verified_at: datetime | None
    rejection_reason: str | None
    created_at: datetime


class AgencyDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agency_id: int
    url: str | None
    uploaded_at: datetime


class AgencyApplyResponse(BaseModel):
    agency: AgencyRead
    admin: UserRead
    document: AgencyDocumentRead


class AgencyRejectRequest(BaseModel):
    reason: str

class AgencyCoverageCreate(BaseModel):
    emergency_type: EmergencyType


class AgencyCoverageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agency_id: int
    emergency_type: EmergencyType
    active: bool


class AgencyListResponse(BaseModel):
    data: list[AgencyRead]
    total: int
    page: int
    page_size: int
    pages: int
