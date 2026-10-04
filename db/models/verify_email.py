from sqlmodel import SQLModel, Field

class VerifyEmail(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="user.id")
    token: str
    otp: str
    