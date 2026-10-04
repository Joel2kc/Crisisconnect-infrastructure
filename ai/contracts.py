from pydantic import BaseModel, Field
from enums.agency import AgencyType
from enums.incident import EmergencyType, IncidentSeverity
from enums.resource import ResourceType


class IncidentTriage(BaseModel):
    """
    The structured output Gemini fills in for one incident.

    Passed straight to response_schema. Field descriptions are read by
    the model as instructions, so they are written as directions rather
    than as documentation.
    """

    summary: str = Field(
        description=(
            "Two or three sentences a dispatcher can act on. "
            "Lead with severity and location."
        )
    )
    emergency_type: EmergencyType = Field(
        description=(
            "The type the description actually describes. Use 'others' only "
            "when it genuinely fits none of the other values."
        )
    )
    severity: IncidentSeverity = Field(
        description=(
            "low = no immediate threat to life. "
            "medium = injury or damage needing response but currently stable. "
            "high_critical = life in immediate danger, or a hazard actively "
            "escalating."
        )
    )
    key_facts: list[str] = Field(
        description=(
            "Discrete operational facts stated in the description. "
            "Do not infer facts that were not stated."
        )
    )
    hazards: list[str] = Field(
        description=(
            "Dangers to whoever arrives: fuel or gas leaks, live power lines, "
            "unstable structures, flood water, hostile crowds, chemicals."
        )
    )
    recommended_agency_types: list[AgencyType] = Field(
        description=(
            "Agency types the description gives a concrete reason to involve. "
            "Never name a specific organisation."
        )
    )
    suggested_skills: list[str] = Field(
        description=(
            "Short lowercase volunteer skill names this incident calls for, "
            "for example 'first aid', 'search and rescue', 'crowd control'."
        )
    )
    required_resources: list[ResourceType] = Field(
        description=(
            "Kinds of equipment the description gives a concrete reason to "
            "send. Name the capability, not a specific vehicle or an amount."
        )
    )
    confidence: float = Field(description="Between 0 and 1.")
    needs_human_review: bool = Field(
        description=(
            "True when the report is internally contradictory, too sparse to "
            "classify, a likely prank, or not an emergency at all."
        )
    )
