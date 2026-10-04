from pydantic import BaseModel

from schemas.agency import AgencyRead
from schemas.volunteer import VolunteerProfileRead


class VerificationAccountsResponse(BaseModel):
    agencies: list[AgencyRead]
    volunteers: list[VolunteerProfileRead]