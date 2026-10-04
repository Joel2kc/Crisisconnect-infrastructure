from datetime import datetime
from enums.agency import AgencyType, AgencyVerificationStatus
from enums.incident import EmergencyType

from sqlalchemy import Column, Integer, ForeignKey
from sqlmodel import SQLModel, Field


class Agency(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    type: AgencyType
    registration_number: str = Field(unique=True, index=True)
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    region: str | None = None

    verification_status: AgencyVerificationStatus = Field(
        default=AgencyVerificationStatus.pending
    )
    verified_by: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("user.id", use_alter=True, name="fk_agency_verified_by"),
            nullable=True
        )
    )
    verified_at: datetime | None = None
    rejection_reason: str | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgencyDocument(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    agency_id: int = Field(foreign_key="agency.id")
    url: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

class AgencyCoverage(SQLModel, table=True):
    """
    Which emergency types an agency handles - the basis for routing for now.
    """
    id: int | None = Field(default=None, primary_key=True)
    agency_id: int = Field(foreign_key="agency.id")
    emergency_type: EmergencyType
    active: bool = Field(default=True)
