from datetime import datetime

from fastapi import HTTPException, status
from schemas.user import UserListResponse, UserRead
from schemas.admin import VerificationAccountsResponse
from sqlmodel import select, Session, func
from enums.user import UserRole
from db.models.user_model import User
from db.models.agency_model import Agency
from db.models.volunteer_model import VolunteerProfile
from schemas.agency import (
    AgencyListResponse,
    AgencyRead,
)
from schemas.volunteer import VolunteerProfileRead
from enums.agency import AgencyVerificationStatus, AgencyType

def get_users(
    session: Session,
    page: int = 1,
    page_size: int = 20,
    role: UserRole | None = None,
    is_active: bool | None = None,
    agency_id: int | None = None,
) -> UserListResponse:

    query = select(User)

    if role is not None:
        query = query.where(User.role == role)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    if agency_id is not None:
        query = query.where(User.agency_id == agency_id)

    # Total number of matching users
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()

    # Pagination
    offset = (page - 1) * page_size

    users = session.exec(
        query
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
    ).all()

    pages = (total + page_size - 1) // page_size

    return UserListResponse(
        data=[UserRead.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
    
def get_agencies(
    session: Session,
    page: int = 1,
    page_size: int = 20,
    verification_status: AgencyVerificationStatus | None = None,
    agency_type: AgencyType | None = None,
    region: str | None = None,
) -> AgencyListResponse:

    query = select(Agency)

    if verification_status is not None:
        query = query.where(
            Agency.verification_status == verification_status
        )

    if agency_type is not None:
        query = query.where(
            Agency.type == agency_type
        )

    if region is not None:
        query = query.where(
            Agency.region == region
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()

    offset = (page - 1) * page_size

    agencies = session.exec(
        query
        .order_by(Agency.created_at.desc())
        .offset(offset)
        .limit(page_size)
    ).all()

    pages = (total + page_size - 1) // page_size

    return AgencyListResponse(
        data=[
            AgencyRead.model_validate(agency)
            for agency in agencies
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def verify_agency(session: Session, agency_id: int, admin: User) -> Agency:
    agency = session.get(Agency, agency_id)
    if not agency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found.")

    if agency.verification_status != AgencyVerificationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agency is already {agency.verification_status.value}.",
        )

    agency.verification_status = AgencyVerificationStatus.verified
    agency.verified_by = admin.id
    agency.verified_at = datetime.utcnow()
    session.add(agency)

    staff = session.exec(select(User).where(User.agency_id == agency_id)).all()
    for member in staff:
        member.is_active = True
        session.add(member)

    session.commit()
    session.refresh(agency)
    return agency


def reject_agency(session: Session, agency_id: int, reason: str, admin: User) -> Agency:
    agency = session.get(Agency, agency_id)
    if not agency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found.")

    if agency.verification_status != AgencyVerificationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agency is already {agency.verification_status.value}.",
        )

    agency.verification_status = AgencyVerificationStatus.rejected
    agency.verified_by = admin.id
    agency.verified_at = datetime.utcnow()
    agency.rejection_reason = reason
    session.add(agency)

    session.commit()
    session.refresh(agency)
    return agency


def verify_volunteer(
    session: Session,
    volunteer_id: int,
    admin: User,
) -> VolunteerProfileRead:
    profile = session.get(VolunteerProfile, volunteer_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volunteer profile not found.",
        )

    if profile.verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Volunteer is already verified.",
        )

    profile.verified = True
    profile.verified_by = admin.id
    profile.verified_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)

    return VolunteerProfileRead.model_validate(profile)


def suspend_volunteer(
    session: Session,
    volunteer_id: int,
    admin: User,
) -> VolunteerProfileRead:
    profile = session.get(VolunteerProfile, volunteer_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volunteer profile not found.",
        )

    if not profile.verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Volunteer is not currently verified.",
        )

    profile.verified = False
    profile.verified_by = admin.id
    profile.verified_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)

    return VolunteerProfileRead.model_validate(profile)

def awaiting_verification(
    session: Session,
    admin: User,
) -> VerificationAccountsResponse:
    agencies = session.exec(
        select(Agency)
        .where(Agency.verification_status == AgencyVerificationStatus.pending)
        .order_by(Agency.created_at.desc())
    ).all()
    volunteers = session.exec(
        select(VolunteerProfile)
        .where(VolunteerProfile.verified.is_(False))
        .order_by(VolunteerProfile.created_at.desc())
    ).all()

    return VerificationAccountsResponse(
        agencies=[AgencyRead.model_validate(agency) for agency in agencies],
        volunteers=[
            VolunteerProfileRead.model_validate(profile)
            for profile in volunteers
        ],
    )


def verified_accounts(
    session: Session,
    admin: User,
) -> VerificationAccountsResponse:
    agencies = session.exec(
        select(Agency)
        .where(Agency.verification_status == AgencyVerificationStatus.verified)
        .order_by(Agency.created_at.desc())
    ).all()
    volunteers = session.exec(
        select(VolunteerProfile)
        .where(VolunteerProfile.verified.is_(True))
        .order_by(VolunteerProfile.created_at.desc())
    ).all()

    return VerificationAccountsResponse(
        agencies=[AgencyRead.model_validate(agency) for agency in agencies],
        volunteers=[
            VolunteerProfileRead.model_validate(profile)
            for profile in volunteers
        ],
    )


def get_account_by_id(
    session: Session,
    user_id: int,
    admin: User,
) -> UserRead:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )

    return UserRead.model_validate(user)