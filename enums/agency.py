from enum import Enum


class AgencyType(str, Enum):
    fire_service = "fire_service"
    emergency_medical_services = "emergency_medical_services"
    ngo = "ngo"
    police = "police"
    nema = "nema"


class AgencyVerificationStatus(str, Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"
    suspended = "suspended"