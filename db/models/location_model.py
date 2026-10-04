from datetime import datetime

from sqlmodel import Field, SQLModel

from enums.location import AssigneeKind


class LocationPing(SQLModel, table=True):
    """
    One position report from a responder or volunteer on their way to an
    incident.

    Written only while an assignment is open and stops the moment it
    closes - this is a movement history of real people, including
    civilian volunteers, so it is deliberately scoped to the job they
    agreed to attend and nothing else. Prune it on a schedule; roughly
    twenty active assignees pinging every twenty seconds is 3,600 rows
    an hour.
    """

    id: int | None = Field(default=None, primary_key=True)

    incident_id: int = Field(foreign_key="incident.id", index=True)

    assignee_kind: AssigneeKind = Field(index=True)
    assignment_id: int = Field(index=True)

    latitude: float
    longitude: float
    accuracy_m: float | None = None
    recorded_at: datetime
    received_at: datetime = Field(default_factory=datetime.utcnow)
    distance_m: float | None = None
    triggered_transition: bool = Field(default=False, index=True)
