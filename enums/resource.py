from enum import Enum


class ResourceType(str, Enum):
    """The four tabs at the top of the add-resource form."""

    vehicle = "vehicle"
    medical_equipment = "medical_equipment"
    supplies = "supplies"
    communications = "communications"


class ResourceCategory(str, Enum):
    """
    Every category across all four resource types.

    One enum rather than four because a single database column has to
    hold whichever was chosen. Which categories are legal for which type
    is expressed by CATEGORIES_BY_TYPE below and enforced on write, so
    an invalid pairing (a 'fire_truck' filed as 'supplies') cannot be
    stored even though the column itself would accept it.
    """

    # Vehicle
    ambulance = "ambulance"
    rescue_vehicle = "rescue_vehicle"
    fire_truck = "fire_truck"
    police_vehicle = "police_vehicle"
    patrol_vehicle = "patrol_vehicle"
    utility_vehicle = "utility_vehicle"

    # Medical equipment
    first_aid = "first_aid"
    patient_care = "patient_care"
    diagnostic = "diagnostic"
    life_support = "life_support"

    # Supplies
    medical_supplies = "medical_supplies"
    safety_equipment = "safety_equipment"
    rescue_supplies = "rescue_supplies"
    protective_equipment = "protective_equipment"
    food_and_water = "food_and_water"

    # Communications
    radio = "radio"
    satellite_communication = "satellite_communication"
    mobile_communication = "mobile_communication"
    emergency_beacon = "emergency_beacon"

    # Offered on every tab.
    other = "other"


CATEGORIES_BY_TYPE: dict[ResourceType, list[ResourceCategory]] = {
    ResourceType.vehicle: [
        ResourceCategory.ambulance,
        ResourceCategory.rescue_vehicle,
        ResourceCategory.fire_truck,
        ResourceCategory.police_vehicle,
        ResourceCategory.patrol_vehicle,
        ResourceCategory.utility_vehicle,
        ResourceCategory.other,
    ],
    ResourceType.medical_equipment: [
        ResourceCategory.first_aid,
        ResourceCategory.patient_care,
        ResourceCategory.diagnostic,
        ResourceCategory.life_support,
        ResourceCategory.other,
    ],
    ResourceType.supplies: [
        ResourceCategory.medical_supplies,
        ResourceCategory.safety_equipment,
        ResourceCategory.rescue_supplies,
        ResourceCategory.protective_equipment,
        ResourceCategory.food_and_water,
        ResourceCategory.other,
    ],
    ResourceType.communications: [
        ResourceCategory.radio,
        ResourceCategory.satellite_communication,
        ResourceCategory.mobile_communication,
        ResourceCategory.emergency_beacon,
        ResourceCategory.other,
    ],
}


class ResourceCondition(str, Enum):
    good = "good"
    fair = "fair"
    poor = "poor"


class FuelLevel(str, Enum):
    """
    Fuel or battery level. Optional, and 'not_applicable' exists because
    most supplies and medical equipment have neither.
    """

    full = "full"
    high = "high"
    medium = "medium"
    low = "low"
    critical = "critical"
    not_applicable = "not_applicable"


FUEL_LEVEL_PERCENTAGES: dict[FuelLevel, str] = {
    FuelLevel.full: "100%",
    FuelLevel.high: "75%",
    FuelLevel.medium: "50%",
    FuelLevel.low: "25%",
    FuelLevel.critical: "<=10%",
    FuelLevel.not_applicable: "",
}
