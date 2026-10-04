from pydantic import BaseModel

class Otp(BaseModel):
  otp: str