from enum import Enum


class AvailabilityStatus(str, Enum):
    weekdays = "weekdays"
    weekends = "weekends"
    emergencies_only = "emergencies_only"
