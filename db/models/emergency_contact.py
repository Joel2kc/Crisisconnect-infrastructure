from sqlmodel import SQLModel, Field
from datetime import datetime


class EmergencyContact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    phone_number: str = Field(unique=True)
    location: str
    category_id: int = Field(foreign_key="emergencycategory.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
