from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Request,
    UploadFile,
    File,
    Form,
    Query,
    HTTPException,
    status
)

from core.dependencies import require_role, get_current_user
from core.session_dependency import sessionDep
from rate_limiter.rate_limiter import limiter
from schemas.agency import (
    AgencyApplyRequest,
    AgencyApplyResponse,
    AgencyDocumentRead,
    AgencyRead,
    AgencyCoverageCreate,
    AgencyCoverageRead,
    AgencyListResponse,
)
from services.agency_service import (
    apply_for_agency,
    add_agency_document,
    _get_pending_agency_or_raise,
    authorize_agency_document_access,
)
from services.admin_service import get_agencies
from services.file_storage_service import upload_file_to_s3
from services.agency_email_service import (
    send_agency_application_received_email,
    send_responder_added_email,
)
from typing import Annotated
from db.models.user_model import User
from db.models.agency_model import Agency
from enums.user import UserRole
from services.agency_coverage_service import (
    add_agency_coverage,
    list_agency_coverage,
    remove_agency_coverage,
)
from pydantic import EmailStr
from enums.agency import AgencyType, AgencyVerificationStatus
from schemas.agency_dashboard import AgencyDashboardResponse
from services.agency_dashboard_service import get_agency_dashboard
from schemas.responder import ResponderCreate, ResponderRead, ResponderCreationResult, ResponderListResponse
from services.responder_service import create_responder, get_agency_responders
from enums.responder import ResponderAvailabilityStatus, ResponderSortBy, SortOrder



agency_router = APIRouter(
    prefix="/api/v1/agencies",
    tags=["Agencies"],
)

AdminUser = Annotated[User, Depends(require_role(UserRole.crisis_connect_admin))]
CurrentUser = Annotated[User, Depends(get_current_user)]
AgencyUser = Annotated[
    User,
    Depends(
        require_role(
            UserRole.agency_admin,
            UserRole.agency_dispatcher,
        )
    )
]
AgencyAdmin = Annotated[User, Depends(require_role(UserRole.agency_admin))]


@agency_router.get("", response_model=AgencyListResponse)
def list_agencies(
    session: sessionDep,
    admin: AdminUser,

    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),

    verification_status: AgencyVerificationStatus | None = Query(None),
    agency_type: AgencyType | None = Query(None),
    region: str | None = Query(None),
):
    return get_agencies(
        session=session,
        page=page,
        page_size=page_size,
        verification_status=verification_status,
        agency_type=agency_type,
        region=region,
    )

@agency_router.post("/apply", response_model=AgencyApplyResponse, status_code=201)
@limiter.limit("5/hour")
def apply(
    request: Request,
    session: sessionDep,
    background_tasks: BackgroundTasks,

    # Organization details
    name: str = Form(...),
    type: AgencyType = Form(...),
    registration_number: str = Form(...),
    org_email: EmailStr | None = Form(None),
    phone: str | None = Form(None),
    address: str | None = Form(None),
    region: str | None = Form(None),

    # Admin details
    admin_full_name: str = Form(...),
    admin_email: EmailStr = Form(...),
    admin_phone: str = Form(...),
    admin_password: str = Form(...),

    # Supporting document
    document: UploadFile = File(...),
):
    """
    Agency onboarding form submission, creates the Agency (pending
    verification) and its first admin account (inactive) together,
    also uploads the supporting document in one request.
    It is rate-limited since it is a public, unauthenticated endpoint.
    """
    payload = AgencyApplyRequest(
        name=name,
        type=type,
        registration_number=registration_number,
        org_email=org_email,
        phone=phone,
        address=address,
        region=region,
        admin_full_name=admin_full_name,
        admin_email=admin_email,
        admin_phone=admin_phone,
        admin_password=admin_password,
    )
    result = apply_for_agency(session, payload, document)

    # Email is sent in the background so a slow/unavailable SMTP server
    # never delays or fails this response. The agency and admin are already
    # created by this point regardless of whether the email goes out.
    background_tasks.add_task(
        send_agency_application_received_email,
        result.admin.email,
        result.agency.name,
    )
    return result


@agency_router.post(
    "/{agency_id}/documents", response_model=AgencyDocumentRead, status_code=201
)
@limiter.limit("10/hour")
def upload_document(
    request: Request,
    agency_id: int,
    session: sessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """
    Adds a supporting document to an agency, after the initial apply -
    e.g. an updated license. Restricted to this agency's own admin (or
    Crisis Connect Admin).
    """

    agency = session.get(Agency, agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found.")
 
    authorize_agency_document_access(agency, current_user)

    file_url = upload_file_to_s3(file, agency.id)

    return add_agency_document(session, agency.id, file_url)


@agency_router.post(
    "/{agency_id}/coverage", response_model=AgencyCoverageRead, status_code=201
)
def add_coverage(
    agency_id: int,
    payload: AgencyCoverageCreate,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Agency admin (own agency only) or Crisis Connect Admin. Declares an
    emergency type this agency responds to — the basis for incident
    routing (see AgencyCoverage / create_incident).
    """
    return add_agency_coverage(session, agency_id, payload, current_user)


@agency_router.get("/{agency_id}/coverage", response_model=list[AgencyCoverageRead])
def get_coverage(agency_id: int, session: sessionDep):
    return list_agency_coverage(session, agency_id)


@agency_router.delete("/{agency_id}/coverage/{coverage_id}", status_code=204)
def delete_coverage(
    agency_id: int,
    coverage_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    remove_agency_coverage(session, agency_id, coverage_id, current_user)


@agency_router.get(
    "/me/dashboard",
    response_model=AgencyDashboardResponse,
)
def agency_dashboard(
    session: sessionDep,
    current_user: AgencyUser,
):
    if current_user.agency_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an agency.",
        )

    return get_agency_dashboard(
        session=session,
        agency_id=current_user.agency_id,
    )

@agency_router.post(
    "/responders",
    response_model=ResponderCreationResult,
    status_code=201,
)
def add_responder(
    payload: ResponderCreate,
    session: sessionDep,
    current_user: AgencyAdmin,
    background_tasks: BackgroundTasks,
):
    if current_user.agency_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an agency.",
        )
    
    agency = session.get(Agency, current_user.agency_id)
    if not agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agency not found.",
        )

    result = create_responder(
        session=session,
        agency_id=current_user.agency_id,
        payload=payload,
    )

    background_tasks.add_task(
        send_responder_added_email,
        result.responder.email,
        result.responder.full_name,
        agency.name,
        result.temporary_password,
    )

    return result


@agency_router.get(
    "/responders",
    response_model=ResponderListResponse,
    status_code=status.HTTP_200_OK,
)
def get_responders(
    session: sessionDep,
    current_user: AgencyUser,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    availability_status: ResponderAvailabilityStatus | None = Query(None),
    sort_by: ResponderSortBy = Query(ResponderSortBy.created_at),
    sort_order: SortOrder = Query(SortOrder.desc),
):
    if current_user.agency_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an agency.",
        )

    return get_agency_responders(
        session=session,
        agency_id=current_user.agency_id,
        page=page,
        limit=limit,
        search=search,
        availability_status=availability_status,
        sort_by=sort_by,
        sort_order=sort_order,
    )
