from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from enums.resource import (
    CATEGORIES_BY_TYPE,
    FUEL_LEVEL_PERCENTAGES,
    FuelLevel,
    ResourceCategory,
    ResourceCondition,
    ResourceType,
)


def _check_category(
    resource_type: ResourceType | None,
    category: ResourceCategory | None,
) -> None:
    """
    Rejects a category that does not belong to the chosen type.

    The form narrows the Category dropdown once a tab is picked, but the
    API is also called by things that are not the form. Without this a
    fire truck could be filed under 'supplies' and silently vanish from
    every vehicle listing.
    """
    if resource_type is None or category is None:
        return

    allowed = CATEGORIES_BY_TYPE[resource_type]
    if category not in allowed:
        names = ", ".join(c.value for c in allowed)
        raise ValueError(
            f"'{category.value}' is not a valid category for "
            f"'{resource_type.value}'. Valid categories are: {names}."
        )


class ResourceCreateRequest(BaseModel):
    resource_type: ResourceType
    name: str = Field(min_length=1, max_length=200)
    asset_number: str | None = Field(default=None, max_length=100)
    # Zero is allowed: a depleted supply line is worth keeping on the
    # register precisely so its absence is visible.
    quantity: int = Field(ge=0)
    category: ResourceCategory
    condition: ResourceCondition
    location: str = Field(min_length=1, max_length=200)
    fuel_level: FuelLevel | None = None
    purchase_date: date
    next_maintenance_date: date
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_resource(self) -> "ResourceCreateRequest":
        _check_category(self.resource_type, self.category)

        # A maintenance date before the purchase date is data entry going
        # wrong, not an overdue service. Past dates on their own are fine -
        # an overdue item is exactly what an agency needs to see.
        if self.next_maintenance_date < self.purchase_date:
            raise ValueError(
                "next_maintenance_date cannot be earlier than purchase_date."
            )
        return self


class ResourceUpdateRequest(BaseModel):
    """
    Every field optional - a PATCH sends only what changed.

    resource_type and category are validated together against whatever
    the resource will look like after the merge, which the service does,
    because a PATCH changing only the type has to be checked against the
    category already stored.
    """

    resource_type: ResourceType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    asset_number: str | None = Field(default=None, max_length=100)
    quantity: int | None = Field(default=None, ge=0)
    category: ResourceCategory | None = None
    condition: ResourceCondition | None = None
    location: str | None = Field(default=None, min_length=1, max_length=200)
    fuel_level: FuelLevel | None = None
    purchase_date: date | None = None
    next_maintenance_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agency_id: int

    resource_type: ResourceType
    name: str
    asset_number: str | None
    quantity: int
    category: ResourceCategory
    condition: ResourceCondition

    location: str
    fuel_level: FuelLevel | None

    purchase_date: date
    next_maintenance_date: date

    notes: str | None
    # A temporary presigned HTTPS URL, not the stored s3:// reference.
    # None when no image was uploaded, and also when S3 is unreachable -
    # a missing thumbnail must not fail the whole listing.
    image_url: str | None

    created_at: datetime
    updated_at: datetime


class ResourceListResponse(BaseModel):
    data: list[ResourceRead]
    total: int
    page: int
    page_size: int
    pages: int


class CategoryOption(BaseModel):
    value: ResourceCategory
    label: str


class ResourceTypeOption(BaseModel):
    value: ResourceType
    label: str
    categories: list[CategoryOption]


class FuelLevelOption(BaseModel):
    value: FuelLevel
    label: str
    # "100%", "75%" ... empty for not_applicable.
    percentage: str


class ConditionOption(BaseModel):
    value: ResourceCondition
    label: str


class ResourceOptionsResponse(BaseModel):
    """
    Everything the add-resource form needs to render its dropdowns.

    Exists so the dependent Category dropdown is driven by the server
    rather than by a hardcoded copy in each client, which is how the app
    and the API end up disagreeing about what is valid.
    """

    resource_types: list[ResourceTypeOption]
    conditions: list[ConditionOption]
    fuel_levels: list[FuelLevelOption]


def _humanise(value: str) -> str:
    return value.replace("_", " ").title()


def build_options() -> ResourceOptionsResponse:
    return ResourceOptionsResponse(
        resource_types=[
            ResourceTypeOption(
                value=resource_type,
                label=_humanise(resource_type.value),
                categories=[
                    CategoryOption(value=category, label=_humanise(category.value))
                    for category in categories
                ],
            )
            for resource_type, categories in CATEGORIES_BY_TYPE.items()
        ],
        conditions=[
            ConditionOption(value=condition, label=_humanise(condition.value))
            for condition in ResourceCondition
        ],
        fuel_levels=[
            FuelLevelOption(
                value=level,
                label=_humanise(level.value),
                percentage=FUEL_LEVEL_PERCENTAGES[level],
            )
            for level in FuelLevel
        ],
    )
