from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from enums.volunteer_assignment import VolunteerAssignmentStatus


class IncidentVolunteer(SQLModel, table=True):
    """
    One volunteer invited to one incident by one agency.

    The counterpart to ResponderAssignment, and deliberately not the same
    table. A responder is dispatched and goes; a volunteer is asked and
    may say no, so this row is a conversation with two ends: the agency
    invites, the volunteer answers from their dashboard.
    """

    id: int | None = Field(default=None, primary_key=True)

    incident_id: int = Field(foreign_key="incident.id", index=True)
    volunteer_id: int = Field(foreign_key="volunteerprofile.id", index=True)

    # Which agency asked. Volunteers belong to no agency, so without this
    # there is no way to tell whose invitation it was when an incident is
    # routed to several agencies at once.
    agency_id: int = Field(foreign_key="agency.id", index=True)

    # NOT NULL with no default. Inviting a civilian toward a scene with
    # live power lines is a decision a person owns, and no AI code path
    # can write this row because no AI code path has a user id.
    invited_by: int = Field(foreign_key="user.id")

    status: VolunteerAssignmentStatus = Field(
        default=VolunteerAssignmentStatus.invited, index=True
    )

    # Why this volunteer surfaced, frozen at invite time. The analysis can
    # be re-run and the skills can change; what the dispatcher saw when
    # they made the call should not.
    matched_skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Free text from the agency - a meeting point, what to bring.
    note: str | None = None
    # The volunteer's own words when declining, so a dispatcher learns
    # whether it was a 'not today' or a 'never ask me again'.
    response_note: str | None = None

    invited_at: datetime = Field(default_factory=datetime.utcnow)
    responded_at: datetime | None = None
    completed_at: datetime | None = None
