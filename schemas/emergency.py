from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmergencyCategoryCreate(BaseModel):
    name: str
    description: str


class EmergencyCategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class EmergencyCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EmergencyContactCreate(BaseModel):
    name: str
    phone_number: str
    location: str
    category_id: int


class EmergencyContactUpdate(BaseModel):
    name: str | None = None
    phone_number: str | None = None
    location: str | None = None
    category_id: int | None = None


class EmergencyContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone_number: str
    location: str
    category_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EmergencyCategoryWithContacts(BaseModel):
    """A category together with every active contact that belongs to it."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    contacts: list[EmergencyContactRead]
