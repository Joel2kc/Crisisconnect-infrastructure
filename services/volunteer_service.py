from datetime import datetime
from fastapi import HTTPException, status
from sqlmodel import Session, select

from core.security import hash_password
from db.models.user_model import User
from db.models.volunteer_model import (
    Skill,
    VolunteerProfile,
    VolunteerSkill,
)
from enums.user import UserRole
from schemas.volunteer import (
    VolunteerRegisterRequest,
    VolunteerRegisterResponse,
    VolunteerSkillRead,
    VolunteerProfileRead,
    VolunteerProfileUpdateRequest,
    SkillRead,
    SkillCreate
)


def register_volunteer(
    session: Session,
    payload: VolunteerRegisterRequest,
) -> VolunteerRegisterResponse:

    # 1. Check whether the email is already registered
    existing_user = session.exec(
        select(User).where(User.email == payload.email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # 2. Resolve all requested skills before creating anything else.
    # Each entry is either an existing skill_id, or a brand-new
    # skill_name (the frontend keeps newly-typed skills purely in
    # local state until Finish Signup, so this is where they actually
    # get created - atomically with the rest of registration, so a
    # skill never ends up created if the registration itself fails).
    skills = []

    for skill_data in payload.skills:
        if skill_data.skill_id is not None:
            skill = session.get(Skill, skill_data.skill_id)

            if not skill:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Skill with ID {skill_data.skill_id} not found.",
                )
        else:
            skill_name = skill_data.skill_name.strip()

            if not skill_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Skill name cannot be empty."
                )

            skill = session.exec(
                select(Skill).where(Skill.name.ilike(skill_name))
            ).first()
 
            if not skill:
                skill = Skill(name=skill_name)
                session.add(skill)
                session.flush()  # get skill.id without committing yet
        skills.append(skill)

    # 3. Create the user account
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=UserRole.volunteer,
        is_active=True,
    )

    session.add(user)
    session.flush()

    # 4. Create volunteer profile
    profile = VolunteerProfile(
        user_id=user.id,
        bio=payload.bio,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        address=payload.address,
        certifications=payload.certifications,
        availability_status=payload.availability_status,
        verified=False,
    )

    session.add(profile)
    session.flush()

    # 5. Create volunteer-skill relationships
    volunteer_skills = []

    for skill in skills:
        volunteer_skill = VolunteerSkill(
            volunteer_id=profile.id,
            skill_id=skill.id,
        )

        session.add(volunteer_skill)
        volunteer_skills.append(volunteer_skill)

    # 6. Commit complete registration
    session.commit()

    # 7. Refresh records
    session.refresh(user)
    session.refresh(profile)

    for volunteer_skill in volunteer_skills:
        session.refresh(volunteer_skill)

    return VolunteerRegisterResponse(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        profile=VolunteerProfileRead.model_validate(profile),
        skills=[
            VolunteerSkillRead.model_validate(skill)
            for skill in volunteer_skills
        ],
    )


def get_skills(session: Session) -> list[SkillRead]:
    skills = session.exec(
        select(Skill).order_by(Skill.id)
    ).all()

    return [
        SkillRead.model_validate(skill)
        for skill in skills
    ]


def update_volunteer_profile(
    session: Session,
    volunteer_id: int,
    payload: VolunteerProfileUpdateRequest,
) -> VolunteerProfileRead:

    profile = session.get(VolunteerProfile, volunteer_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volunteer profile not found.",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(profile, field, value)

    profile.updated_at = datetime.utcnow()

    session.add(profile)
    session.commit()
    session.refresh(profile)

    return VolunteerProfileRead.model_validate(profile)


def create_skill(
    session: Session,
    payload: SkillCreate,
) -> SkillRead:
 
    # Remove unnecessary spaces from the beginning and end.
    skill_name = payload.name.strip()
 
    # No empty skill name allowed.
    if not skill_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skill name cannot be empty.",
        )
 
    # Check for an existing skill case-insensitively.
    existing_skill = session.exec(
        select(Skill).where(Skill.name.ilike(skill_name))
    ).first()
 
    if existing_skill:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A skill with this name already exists.",
        )
 
    skill = Skill(name=skill_name)
 
    session.add(skill)
    session.commit()
    session.refresh(skill)
 
    return SkillRead.model_validate(skill)




