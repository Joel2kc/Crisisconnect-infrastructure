from pydantic import BaseModel, EmailStr, ConfigDict, model_validator
from datetime import datetime
from db.models.user_model import UserRole

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    phone: str | None
    role: UserRole
    agency_id: int | None
    is_active: bool
    email_verified: bool
    created_at: datetime

class ForgotPasswordDetails(BaseModel):
  email: str

class ConfirmResetOtpDetails(BaseModel):
  otp: str

class ResetPasswordDetails(BaseModel):
  new_password: str
  confirm_password: str

  @model_validator(mode="after")
  def passwords_match(self):
    if self.new_password != self.confirm_password:
      raise ValueError("Passwords do not match")
    return self

class RefreshTokenDetails(BaseModel):
  refresh_token: str
  
class LoginDetails(BaseModel):
  email: str
  password: str
  
class RegistrationDetails(LoginDetails):
  full_name: str
  phone: str | None = None
  role: UserRole = UserRole.citizen

class UserListResponse(BaseModel):
    data: list[UserRead]
    total: int
    page: int
    page_size: int
    pages: int