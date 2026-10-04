from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import SQLModel, Field

from enums.volunteer import AvailabilityStatus


class VolunteerProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        unique=True,
        index=True,
    )

    bio: str | None = None
    date_of_birth: datetime | None = None
    gender: str | None = None
    address: str | None = None
    certifications: str | None = None

    availability_status: list[AvailabilityStatus] = Field(
        default_factory=lambda: [AvailabilityStatus.weekdays],
        sa_column=Column(
            ARRAY(
                SAEnum(
                    AvailabilityStatus,
                    name="availabilitystatus",
                )
            ),
            nullable=False,
        ),
    )

    verified: bool = Field(default=False)

    verified_by: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey(
                "user.id",
                use_alter=True,
                name="fk_volunteer_verified_by",
            ),
            nullable=True,
        ),
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    verified_at: datetime | None = None


class Skill(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    name: str = Field(unique=True, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class VolunteerSkill(SQLModel, table=True):
    volunteer_id: int = Field(
        foreign_key="volunteerprofile.id",
        primary_key=True,
    )

    skill_id: int = Field(
        foreign_key="skill.id",
        primary_key=True,
    )
