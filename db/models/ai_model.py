from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import SQLModel, Field

from enums.ai import AnalysisStatus
from enums.incident import EmergencyType, IncidentSeverity


class IncidentAnalysis(SQLModel, table=True):
    """
    Gemini's reading of one incident. Advisory only.

    Nothing in the existing incident lifecycle reads this table, so it
    cannot affect routing, Incident.status, or dispatch. The status
    machine in incident_service remains the single source of truth.
    One row per incident.
    """

    id: int | None = Field(default=None, primary_key=True)
    incident_id: int = Field(foreign_key="incident.id", unique=True, index=True)
    status: AnalysisStatus = Field(default=AnalysisStatus.pending, index=True)

    # --- what Gemini read ---
    summary: str | None = None
    suggested_emergency_type: EmergencyType | None = None
    suggested_severity: IncidentSeverity | None = None
    key_facts: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    hazards: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    # Free-text skill names, matched against the Skill table when volunteer
    # ranking is added later.
    suggested_skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    recommended_agency_types: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    # ResourceType values. Stored as plain strings so an enum added later
    # cannot make an old row unreadable; matched against AgencyResource to
    # work out what an agency actually holds and what it is missing.
    required_resources: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    confidence: float | None = None
    needs_human_review: bool = Field(default=False)

    # --- the actual product: where Gemini disagrees with the citizen ---
    # type_disagreement matters most: routing keys on emergency_type, and
    # 'others' matches no AgencyCoverage row at all, so those incidents
    # currently reach nobody.
    type_disagreement: bool = Field(default=False, index=True)
    # Escalation only. A model lowering a severity a person chose is not
    # something we surface as actionable.
    severity_escalation: bool = Field(default=False, index=True)

    # --- observability: what Gemini costs you, queryable in SQL ---
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    error: str | None = None
    attempts: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
