from sqlmodel import SQLModel, Field

class RefreshToken(SQLModel, table=True):
  id: int | None = Field(default=None, primary_key=True)
  refresh_token: str
  
  user_id: int = Field(foreign_key="user.id")
