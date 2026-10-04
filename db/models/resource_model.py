from datetime import date, datetime

from sqlmodel import Field, SQLModel

from enums.resource import (
    FuelLevel,
    ResourceCategory,
    ResourceCondition,
    ResourceType,
)


class AgencyResource(SQLModel, table=True):
    """
    One line of an agency's inventory - a single vehicle, or a stock of
    supplies held as a quantity.

    Owned and maintained by the agency itself. Nothing else in the
    schema references it yet: it is a register, not an assignment, so
    deleting a row cannot orphan an incident.
    """

    id: int | None = Field(default=None, primary_key=True)
    agency_id: int = Field(foreign_key="agency.id", index=True)

    resource_type: ResourceType = Field(index=True)
    name: str
    asset_number: str | None = Field(default=None, index=True)
    quantity: int
    category: ResourceCategory = Field(index=True)
    condition: ResourceCondition = Field(index=True)
    location: str
    fuel_level: FuelLevel | None = Field(default=None)
    purchase_date: date
    next_maintenance_date: date
    notes: str | None = None
    image_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
