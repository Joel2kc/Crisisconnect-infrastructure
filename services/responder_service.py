from fastapi import HTTPException, status
from sqlmodel import Session, select, func
from schemas.responder import ResponderCreate, ResponderRead, ResponderCreationResult, ResponderListResponse
from core.temporary_password import generate_temporary_password
from core.security import hash_password
from db.models.user_model import User
from db.models.agency_model import Agency
from db.models.responder_model import ResponderProfile, ResponderSkill
from db.models.volunteer_model import Skill
from enums.user import UserRole
from enums.responder import ResponderAvailabilityStatus, ResponderSortBy, SortOrder
from math import ceil


def create_responder(
    session: Session,
    agency_id: int,
    payload: ResponderCreate,
) -> ResponderCreationResult:

    existing_user = session.exec(
        select(User).where(User.email == payload.email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    temporary_password = generate_temporary_password()
    # agency = session.get(Agency, agency_id)
    # agency_name = agency.name

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(temporary_password),
        role=UserRole.responder,
        agency_id=agency_id,
        is_active=True,
    )

    session.add(user)
    session.flush()

    responder = ResponderProfile(
        user_id=user.id,
        position=payload.position,
        employee_id=payload.employee_id,
        availability_status=ResponderAvailabilityStatus.available,
    )

    session.add(responder)
    session.flush()

    for skill_id in payload.skill_ids:
        skill = session.get(Skill, skill_id)

        if not skill:
            raise HTTPException(
                status_code=404,
                detail=f"Skill with ID {skill_id} not found.",
            )

        session.add(
            ResponderSkill(
                responder_id=responder.id,
                skill_id=skill_id,
            )
        )
    session.commit()
    session.refresh(user)
    session.refresh(responder)

    responder_read = ResponderRead(
        id=responder.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        position=responder.position,
        employee_id=responder.employee_id,
        availability_status=responder.availability_status,
        is_active=user.is_active,
        created_at=responder.created_at,
    )

    return ResponderCreationResult(
        responder=responder_read,
        temporary_password=temporary_password,
    )


def get_agency_responders(
    session: Session,
    agency_id: int,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    availability_status: ResponderAvailabilityStatus | None =  None,
    sort_by: ResponderSortBy = ResponderSortBy.created_at,
    sort_order: SortOrder = SortOrder.desc,
) -> ResponderListResponse:

    statement = (
        select(ResponderProfile, User)
        .join(User, ResponderProfile.user_id == User.id)
        .where(User.agency_id == agency_id)
    )

    # Search by name, email, or employee ID
    if search:
        search_term = f"%{search.strip()}%"
        statement = statement.where(
            (User.full_name.ilike(search_term))
            | (User.email.ilike(search_term))
            | (ResponderProfile.employee_id.ilike(search_term))
        )

    # Filter by availability status
    if availability_status:
        statement = statement.where(
            ResponderProfile.availability_status == availability_status
        )

    # Sorting
    if sort_by == ResponderSortBy.name:
        sort_column = User.full_name
    elif sort_by == ResponderSortBy.created_at:
        sort_column = ResponderProfile.created_at
    elif sort_by == ResponderSortBy.availability_status:
        sort_column = ResponderProfile.availability_status
    elif sort_by == ResponderSortBy.employee_id:
        sort_column = ResponderProfile.employee_id
    else:
        sort_column = ResponderProfile.created_at 

    if sort_order == SortOrder.asc:
        statement = statement.order_by(
            sort_column.asc(),
            ResponderProfile.id.asc(),
        )
    else:
        statement = statement.order_by(
            sort_column.desc(),
            ResponderProfile.id.desc(),
        )

    # Count total records after search and filtering
    count_statement = select(func.count()).select_from(statement.subquery())

    total = session.exec(count_statement).one()

    offset = (page - 1) * limit

    statement = (
        statement
        .offset(offset)
        .limit(limit)
    )

    results = session.exec(statement).all()

    responders = [
        ResponderRead(
            id=responder.id,
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            position=responder.position,
            employee_id=responder.employee_id,
            availability_status=responder.availability_status,
            is_active=user.is_active,
            created_at=responder.created_at,
        )
        for responder, user in results
    ]

    total_pages = ceil(total / limit) if total > 0 else 0

    return ResponderListResponse(
        responders=responders,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )
