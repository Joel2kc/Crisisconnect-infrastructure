import logging
from fastapi import HTTPException, UploadFile, status
from sqlmodel import Session, select

from core.security import hash_password
from db.models.agency_model import Agency, AgencyDocument
from db.models.user_model import User
from schemas.agency import (
    AgencyApplyRequest,
    AgencyApplyResponse,
    AgencyDocumentRead,
)
from enums.agency import AgencyVerificationStatus
from enums.user import UserRole
from datetime import datetime
from services.file_storage_service import upload_file_to_s3, generate_presigned_url

logger = logging.getLogger(__name__)


def apply_for_agency(
    session: Session,
    payload: AgencyApplyRequest,
    document: UploadFile,
) -> AgencyApplyResponse:
    """
    Creates an Agency (pending verification), supporting document and its first admin User
    (inactive until the agency is verified) in a single transaction.
    """

    agency_name_query = select(Agency).where(Agency.name == payload.name)
    existing_agency_name = session.exec(agency_name_query).first()

    if existing_agency_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An agency with this name has already applied.",
        )

    agency_query = select(Agency).where(Agency.registration_number == payload.registration_number)

    existing_agency = session.exec(agency_query).first()
    if existing_agency:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An agency with this registration number has already applied.",
        )

    user_query = select(User).where(User.email == payload.admin_email)

    existing_user = session.exec(user_query).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    agency = Agency(
        name=payload.name,
        type=payload.type,
        registration_number=payload.registration_number,
        email=payload.org_email,
        phone=payload.phone,
        address=payload.address,
        region=payload.region,
    )
    session.add(agency)
    session.flush()

    admin = User(
        full_name=payload.admin_full_name,
        email=payload.admin_email,
        phone=payload.admin_phone,
        password_hash=hash_password(payload.admin_password),
        role=UserRole.agency_admin,
        agency_id=agency.id,
        is_active=False,  # turns to true when the agency is verified
    )
    session.add(admin)

    # Supporting document is uploaded
    file_url = upload_file_to_s3(
        document,
        agency.id,
    )

    # Create document record
    agency_document = AgencyDocument(
        agency_id=agency.id,
        url=file_url,
    )
    session.add(agency_document)

    # Committed after S3 upload has succeeded
    session.commit()
    session.refresh(agency)
    session.refresh(admin)
    session.refresh(agency_document)

    try:
        presigned_url = generate_presigned_url(agency_document.url)
    except HTTPException:
        logger.exception(
            "Failed to generate presigned URL for agency_document_id=%s "
            "(agency_id=%s) — document was saved successfully; only the "
            "temporary view URL is unavailable right now.",
            agency_document.id,
            agency.id,
        )
        presigned_url = None

    return AgencyApplyResponse(
        agency=agency,
        admin=admin,
        document=AgencyDocumentRead(
            id=agency_document.id,
            agency_id=agency_document.agency_id,
            url=presigned_url,
            uploaded_at=agency_document.uploaded_at,
        )
    )


def add_agency_document(session: Session, agency_id: int, url: str) -> AgencyDocument:
    agency = session.get(Agency, agency_id)
    if not agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found."
        )

    document = AgencyDocument(agency_id=agency_id, url=url)
    session.add(document)
    session.commit()
    session.refresh(document)

    return document


def _get_pending_agency_or_raise(session: Session, agency_id: int) -> Agency:
    agency = session.get(Agency, agency_id)
    if not agency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found.")
    if agency.verification_status != AgencyVerificationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agency is already {agency.verification_status.value}.",
        )
    return agency


def authorize_agency_document_access(agency: Agency, actor: User) -> None:
    """
    Only this agency's own admin, or Crisis Connect Admin, can add
    documents.
    """
    if actor.role.value == "crisis_connect_admin":
        return
    if actor.role.value == "agency_admin" and actor.agency_id == agency.id:
        return
 
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only this agency's admin (or Crisis Connect Admin) can upload documents here.",
    )

