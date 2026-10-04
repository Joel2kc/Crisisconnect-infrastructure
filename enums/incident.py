from enum import Enum


class EmergencyType(str, Enum):
    fire = "fire"
    medical = "medical"
    accident = "accident"
    crime = "crime"
    flood = "flood"
    others = "others"


class IncidentSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high_critical = "high_critical"


class IncidentStatus(str, Enum):
    reported = "reported"
    verified = "verified"
    dispatched = "dispatched"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"


class IncidentAgencyRole(str, Enum):
    primary = "primary"
    supporting = "supporting"


class IncidentAgencyStatus(str, Enum):
    notified = "notified"
    verified = "verified"
    dispatched = "dispatched"
    responding = "responding"
    resolved = "resolved"
    declined = "declined"
