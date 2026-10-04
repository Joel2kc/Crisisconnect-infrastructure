from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from enums.user import UserRole
from enums.volunteer import AvailabilityStatus

class VolunteerSkillCreate(BaseModel):
    # Either reference an existing skill by id, or supply a new skill's
    # name - the frontend holds newly-typed skills purely in local state
    # until "Finish Signup", so registration is what actually creates
    # them, atomically with everything else.
    skill_id: int | None = None
    skill_name: str | None = None

    @model_validator(mode="after")
    def one_of_id_or_name(self):
        if not self.skill_id and not self.skill_name:
            raise ValueError("Provide either skill_id or skill_name.")
        if self.skill_id and self.skill_name:
            raise ValueError("Provide only one of skill_id or skill_name, not both.")
        return self

class VolunteerRegisterRequest(BaseModel):
    # User information
    full_name: str
    email: EmailStr
    phone: str
    password: str
    # Volunteer profile information
    bio: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    certifications: str | None = None
    availability_status: list[AvailabilityStatus] = Field(
        default_factory=list
    )
    # Skills
    skills: list[VolunteerSkillCreate] = Field(
        default_factory=list
    )

class VolunteerSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    skill_id: int

class VolunteerProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    bio: str | None
    date_of_birth: date | None
    gender: str | None
    address: str | None
    certifications: str | None
    availability_status: list[AvailabilityStatus]
    verified: bool
    created_at: datetime
    updated_at: datetime

class VolunteerRegisterResponse(BaseModel):
    user_id: int
    full_name: str
    email: EmailStr
    phone: str | None
    role: UserRole
    profile: VolunteerProfileRead
    skills: list[VolunteerSkillRead]

class VolunteerProfileUpdateRequest(BaseModel):
    bio: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    certifications: str | None = None
    availability_status: list[AvailabilityStatus] | None = None

class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime

class SkillCreate(BaseModel):
    name: str
