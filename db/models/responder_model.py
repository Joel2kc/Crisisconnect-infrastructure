from datetime import datetime

from sqlmodel import SQLModel, Field

from enums.responder import (
    ResponderAvailabilityStatus,
    ResponderAssignmentStatus,
    ResponderResponseOutcome,
)


class ResponderProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        unique=True,
        index=True,
    )

    position: str | None = None

    employee_id: str | None = Field(
        default=None,
        index=True,
    )

    availability_status: ResponderAvailabilityStatus = Field(
        default=ResponderAvailabilityStatus.available
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )


class ResponderSkill(SQLModel, table=True):
    responder_id: int = Field(
        foreign_key="responderprofile.id",
        primary_key=True,
    )

    skill_id: int = Field(
        foreign_key="skill.id",
        primary_key=True,
    )


class ResponderAssignment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    responder_id: int = Field(foreign_key="responderprofile.id", index=True)

    incident_id: int = Field(foreign_key="incident.id", index=True)

    assigned_by: int = Field(foreign_key="user.id")

    status: ResponderAssignmentStatus = Field(
        default=ResponderAssignmentStatus.assigned
    )

    response_outcome: ResponderResponseOutcome | None = None

    response_note: str | None = None

    assigned_at: datetime = Field(default_factory=datetime.utcnow)

    started_at: datetime | None = None

    completed_at: datetime | None = None


class ResponderCompletionEvidence(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    assignment_id: int = Field(
        foreign_key="responderassignment.id",
        index=True,
    )

    uploaded_by: int = Field(foreign_key="user.id")

    url: str

    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
