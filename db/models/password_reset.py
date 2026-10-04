from sqlmodel import SQLModel, Field
from datetime import datetime


class PasswordReset(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    otp: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime 
    used: bool = Field(default=False)
