from fastapi import APIRouter, Request

from core.session_dependency import sessionDep
from db.models.user_model import User
from enums.user import UserRole
from rate_limiter.rate_limiter import limiter
from schemas.volunteer import (
    VolunteerRegisterRequest,
    VolunteerRegisterResponse,
    VolunteerProfileRead,
    VolunteerProfileUpdateRequest,
    SkillRead,
    SkillCreate
)
from services.volunteer_service import (
    register_volunteer,
    get_skills,
    update_volunteer_profile,
    create_skill,
)


volunteer_router = APIRouter(
    prefix="/api/v1/volunteers",
    tags=["Volunteers"],
)



@volunteer_router.post(
    "/register",
    response_model=VolunteerRegisterResponse,
    status_code=201,
)
@limiter.limit("5/hour")
def register(
    request: Request,
    payload: VolunteerRegisterRequest,
    session: sessionDep,
):
    """
    Registers a new volunteer, creating the user account,
    volunteer profile, and selected skills.
    """
    return register_volunteer(session, payload)


@volunteer_router.get(
    "/skills",
    response_model=list[SkillRead],
)
def list_skills(
    session: sessionDep,
):
    """
    Returns all available volunteer skills.
    """
    return get_skills(session)


@volunteer_router.patch(
    "/{volunteer_id}",
    response_model=VolunteerProfileRead,
)
def update_profile(
    volunteer_id: int,
    payload: VolunteerProfileUpdateRequest,
    session: sessionDep,
):
    """
    Updates a volunteer profile.
    """
    return update_volunteer_profile(
        session,
        volunteer_id,
        payload,
    )


@volunteer_router.post(
    "/skills",
    response_model=SkillRead,
    status_code=201,
)
@limiter.limit("20/hour")
def add_skill(
    request: Request,
    payload: SkillCreate,
    session: sessionDep,
):
    """
    Adds a new skill to the shared skills list
    """
    return create_skill(session, payload)




