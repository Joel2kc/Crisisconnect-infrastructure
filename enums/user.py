from enum import Enum


class UserRole(str, Enum):
    citizen = "citizen"
    volunteer = "volunteer"
    agency_admin = "agency_admin"
    agency_dispatcher = "agency_dispatcher"
    responder = "responder"
    government_official = "government_official"
    crisis_connect_admin = "crisis_connect_admin"
