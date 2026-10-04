"""
Agency-owned resource inventory: vehicles, medical equipment, supplies
and communications gear.

Every endpoint is scoped to one agency. An agency manages its own
register and nobody else's; Crisis Connect admins see across agencies,
and government officials get read-only visibility, matching how incident
access already works.
"""

import logging
import math
from datetime import date, datetime

from fastapi import HTTPException, UploadFile, status
from sqlmodel import Session, func, select

from db.models.agency_model import Agency
from db.models.resource_model import AgencyResource
from db.models.user_model import User
from enums.resource import CATEGORIES_BY_TYPE, ResourceCategory, ResourceCondition, ResourceType
from enums.user import UserRole
from schemas.resource import (
    ResourceCreateRequest,
    ResourceListResponse,
    ResourceRead,
    ResourceUpdateRequest,
)
from services.file_storage_service import generate_presigned_url, upload_file_to_s3

logger = logging.getLogger(__name__)

# Only an agency's own admin maintains its inventory. Dispatchers and
# responders read it but do not edit it, so a correction during an
# incident cannot be made by whoever happens to be on the console.
_WRITE_ROLES = {UserRole.agency_admin, UserRole.crisis_connect_admin}

# Roles whose access is not limited to a single agency.
_CROSS_AGENCY_ROLES = {UserRole.crisis_connect_admin, UserRole.government_official}

_READ_ROLES = _CROSS_AGENCY_ROLES | {
    UserRole.agency_admin,
    UserRole.agency_dispatcher,
    UserRole.responder,
}

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


def _get_agency_or_404(session: Session, agency_id: int) -> Agency:
    agency = session.get(Agency, agency_id)
    if not agency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found."
        )
    return agency


def _authorize(agency_id: int, actor: User, *, write: bool) -> None:
    allowed = _WRITE_ROLES if write else _READ_ROLES

    if actor.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )

    if actor.role in _CROSS_AGENCY_ROLES:
        return

    if actor.agency_id != agency_id:
      
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage resources belonging to your own agency.",
        )


def _assert_asset_number_free(
    session: Session,
    agency_id: int,
    asset_number: str | None,
    exclude_id: int | None = None,
) -> None:
    """
    An asset tag identifies one thing. Duplicates within an agency defeat
    the point, so they are rejected; the same tag at a different agency is
    fine and common.
    """
    if not asset_number:
        return

    query = select(AgencyResource).where(
        AgencyResource.agency_id == agency_id,
        AgencyResource.asset_number == asset_number,
    )
    if exclude_id is not None:
        query = query.where(AgencyResource.id != exclude_id)

    if session.exec(query).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A resource with asset number '{asset_number}' already "
                "exists for this agency."
            ),
        )


def _validate_image(image: UploadFile) -> None:
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image type. Allowed types are JPEG and PNG.",
        )

    image.file.seek(0, 2)  # SEEK_END
    size = image.file.tell()
    image.file.seek(0)

    if size > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image is too large. Maximum allowed size is 5 MB.",
        )


def _to_read(resource: AgencyResource) -> ResourceRead:
    """
    Swaps the stored s3:// reference for a temporary HTTPS URL.

    A failure to presign yields a resource with no image rather than a
    failed request: S3 being unreachable (or simply unconfigured, as it
    is in local development) must not take out the inventory listing.
    """
    payload = ResourceRead.model_validate(resource)

    if resource.image_url:
        try:
            payload.image_url = generate_presigned_url(resource.image_url)
        except Exception:  # noqa: BLE001 - the listing matters, the thumbnail does not
            logger.warning(
                "could not presign image for resource=%s", resource.id, exc_info=True
            )
            payload.image_url = None

    return payload


def create_resource(
    session: Session,
    agency_id: int,
    payload: ResourceCreateRequest,
    actor: User,
    image: UploadFile | None = None,
) -> ResourceRead:
    _get_agency_or_404(session, agency_id)
    _authorize(agency_id, actor, write=True)
    _assert_asset_number_free(session, agency_id, payload.asset_number)

    image_url = None
    if image is not None and image.filename:
        _validate_image(image)
      
        image_url = upload_file_to_s3(image, agency_id)

    resource = AgencyResource(
        agency_id=agency_id,
        resource_type=payload.resource_type,
        name=payload.name.strip(),
        asset_number=(payload.asset_number or "").strip() or None,
        quantity=payload.quantity,
        category=payload.category,
        condition=payload.condition,
        location=payload.location.strip(),
        fuel_level=payload.fuel_level,
        purchase_date=payload.purchase_date,
        next_maintenance_date=payload.next_maintenance_date,
        notes=payload.notes,
        image_url=image_url,
    )

    session.add(resource)
    session.commit()
    session.refresh(resource)
    return _to_read(resource)


def list_resources(
    session: Session,
    agency_id: int,
    actor: User,
    page: int = 1,
    page_size: int = 20,
    resource_type: ResourceType | None = None,
    category: ResourceCategory | None = None,
    condition: ResourceCondition | None = None,
    search: str | None = None,
    maintenance_due: bool | None = None,
) -> ResourceListResponse:
    _get_agency_or_404(session, agency_id)
    _authorize(agency_id, actor, write=False)

    query = select(AgencyResource).where(AgencyResource.agency_id == agency_id)

    if resource_type is not None:
        query = query.where(AgencyResource.resource_type == resource_type)
    if category is not None:
        query = query.where(AgencyResource.category == category)
    if condition is not None:
        query = query.where(AgencyResource.condition == condition)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            AgencyResource.name.ilike(term) | AgencyResource.asset_number.ilike(term)
        )
    if maintenance_due:
       
        query = query.where(AgencyResource.next_maintenance_date <= date.today())

    total = session.exec(select(func.count()).select_from(query.subquery())).one()

    resources = session.exec(
        query.order_by(AgencyResource.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ResourceListResponse(
        data=[_to_read(resource) for resource in resources],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


def _get_resource_or_404(
    session: Session, agency_id: int, resource_id: int
) -> AgencyResource:
    resource = session.get(AgencyResource, resource_id)
   
    if not resource or resource.agency_id != agency_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found."
        )
    return resource


def get_resource(
    session: Session, agency_id: int, resource_id: int, actor: User
) -> ResourceRead:
    _get_agency_or_404(session, agency_id)
    _authorize(agency_id, actor, write=False)
    return _to_read(_get_resource_or_404(session, agency_id, resource_id))


def update_resource(
    session: Session,
    agency_id: int,
    resource_id: int,
    payload: ResourceUpdateRequest,
    actor: User,
    image: UploadFile | None = None,
) -> ResourceRead:
    _get_agency_or_404(session, agency_id)
    _authorize(agency_id, actor, write=True)
    resource = _get_resource_or_404(session, agency_id, resource_id)

    changes = payload.model_dump(exclude_unset=True)

 
    merged_type = changes.get("resource_type", resource.resource_type)
    merged_category = changes.get("category", resource.category)
    if merged_category not in CATEGORIES_BY_TYPE[merged_type]:
        names = ", ".join(c.value for c in CATEGORIES_BY_TYPE[merged_type])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"'{merged_category.value}' is not a valid category for "
                f"'{merged_type.value}'. Valid categories are: {names}."
            ),
        )

    merged_purchase = changes.get("purchase_date", resource.purchase_date)
    merged_maintenance = changes.get(
        "next_maintenance_date", resource.next_maintenance_date
    )
    if merged_maintenance < merged_purchase:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="next_maintenance_date cannot be earlier than purchase_date.",
        )

    if "asset_number" in changes:
        changes["asset_number"] = (changes["asset_number"] or "").strip() or None
        _assert_asset_number_free(
            session, agency_id, changes["asset_number"], exclude_id=resource.id
        )

    for field, value in changes.items():
        setattr(resource, field, value)

    if image is not None and image.filename:
        _validate_image(image)
       
        resource.image_url = upload_file_to_s3(image, agency_id)

    resource.updated_at = datetime.utcnow()

    session.add(resource)
    session.commit()
    session.refresh(resource)
    return _to_read(resource)


def delete_resource(
    session: Session, agency_id: int, resource_id: int, actor: User
) -> None:
    _get_agency_or_404(session, agency_id)
    _authorize(agency_id, actor, write=True)
    resource = _get_resource_or_404(session, agency_id, resource_id)

   
    session.delete(resource)
    session.commit()
