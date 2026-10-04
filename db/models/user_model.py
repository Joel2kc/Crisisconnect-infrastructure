from sqlmodel import SQLModel, Field

from datetime import datetime
from enums.user import UserRole

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    full_name: str
    email: str = Field(unique=True, index=True)
    phone: str | None = None
    password_hash: str
    role: UserRole
    agency_id: int | None = Field(default=None, foreign_key="agency.id")
    is_active: bool = Field(default=False)

    email_verified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
