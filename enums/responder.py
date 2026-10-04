from enum import Enum


class ResponderAvailabilityStatus(str, Enum):
    available = "available"
    assigned = "assigned"
    unavailable = "unavailable"


class ResponderAssignmentStatus(str, Enum):
    assigned = "assigned"
    en_route = "en_route"
    on_scene = "on_scene"
    complete = "complete"


class ResponderSortBy(str, Enum):
    name = "name"
    created_at = "created_at"
    availability_status = "availability_status"
    employee_id = "employee_id"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class ResponderAssignmentFilter(str, Enum):
    active = "active"
    completed = "completed"


class ResponderResponseOutcome(str, Enum):
    resolved = "resolved"
    stabilized_or_assistance_provided = "stabilized_or_assistance_provided"
    transferred_to_another_agency = "transferred_to_another_agency"
    unable_to_resolve = "unable_to_resolve"
    no_action_required = "no_action_required"
    other = "other"
