from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from core.dependencies import CurrentUser
from core.session_dependency import sessionDep
from enums.resource import FuelLevel, ResourceCategory, ResourceCondition, ResourceType
from schemas.resource import (
    ResourceCreateRequest,
    ResourceListResponse,
    ResourceOptionsResponse,
    ResourceRead,
    ResourceUpdateRequest,
    build_options,
)
from services.resource_service import (
    create_resource,
    delete_resource,
    get_resource,
    list_resources,
    update_resource,
)


resource_router = APIRouter(prefix="/api/v1", tags=["Agency Resources"])


def _as_request(model, **fields):
    """
    Builds a request model from multipart form fields.

    Pydantic's error is re-raised as a 422 so a bad category reads the
    same whether it arrived as JSON or as form data, rather than
    surfacing as an unhandled ValidationError.
    """
    try:
        return model(**fields)
    except ValidationError as exc:
      
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=jsonable_encoder(exc.errors(include_url=False)),
        ) from exc


@resource_router.get("/resources/options", response_model=ResourceOptionsResponse)
def resource_options():
    """
    Everything the add-resource form needs to build its dropdowns.

    Returns each resource type with the categories legal for it, plus the
    condition and fuel-level options with their percentage labels.
    Selecting a type narrows the category list to that type's entry.

    Unauthenticated and static - it describes the form, not any agency's
    data, and clients should fetch it rather than hardcode a copy that
    will eventually disagree with what the API accepts.
    """
    return build_options()


@resource_router.post(
    "/agencies/{agency_id}/resources",
    response_model=ResourceRead,
    status_code=201,
)
def add_resource(
    agency_id: int,
    session: sessionDep,
    current_user: CurrentUser,
    resource_type: ResourceType = Form(...),
    name: str = Form(..., description="Name/Model, e.g. 'Ambulance 2 - Toyota Hiace'"),
    quantity: int = Form(..., ge=0),
    category: ResourceCategory = Form(...),
    condition: ResourceCondition = Form(...),
    location: str = Form(..., description="Base station"),
    purchase_date: date = Form(...),
    next_maintenance_date: date = Form(...),
    asset_number: str | None = Form(None, description="e.g. 'AMB-002'"),
    fuel_level: FuelLevel | None = Form(None),
    notes: str | None = Form(None),
    image: UploadFile | None = File(None, description="JPEG or PNG, max 5MB"),
):
    """
    Adds a resource to an agency's inventory.

    Multipart, so the optional photo arrives with the details in one
    request and the row is only written once the upload has succeeded.

    Restricted to the agency's own admin (and Crisis Connect admins).
    The category must belong to the chosen resource type - see
    GET /api/v1/resources/options for the valid pairings.
    """
    payload = _as_request(
        ResourceCreateRequest,
        resource_type=resource_type,
        name=name,
        asset_number=asset_number,
        quantity=quantity,
        category=category,
        condition=condition,
        location=location,
        fuel_level=fuel_level,
        purchase_date=purchase_date,
        next_maintenance_date=next_maintenance_date,
        notes=notes,
    )
    return create_resource(session, agency_id, payload, current_user, image)


@resource_router.get(
    "/agencies/{agency_id}/resources", response_model=ResourceListResponse
)
def list_agency_resources(
    agency_id: int,
    session: sessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    resource_type: ResourceType | None = Query(None),
    category: ResourceCategory | None = Query(None),
    condition: ResourceCondition | None = Query(None),
    search: str | None = Query(None, description="Matches name or asset number"),
    maintenance_due: bool | None = Query(
        None, description="Only resources whose next maintenance date has passed"
    ),
):
    """
    Lists an agency's inventory, newest first.

    Readable by the agency's own admins, dispatchers and responders, and
    by Crisis Connect admins and government officials across agencies.
    """
    return list_resources(
        session,
        agency_id,
        current_user,
        page=page,
        page_size=page_size,
        resource_type=resource_type,
        category=category,
        condition=condition,
        search=search,
        maintenance_due=maintenance_due,
    )


@resource_router.get(
    "/agencies/{agency_id}/resources/{resource_id}", response_model=ResourceRead
)
def read_resource(
    agency_id: int,
    resource_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    """Fetches one resource. 404 if it belongs to a different agency."""
    return get_resource(session, agency_id, resource_id, current_user)


@resource_router.patch(
    "/agencies/{agency_id}/resources/{resource_id}", response_model=ResourceRead
)
def edit_resource(
    agency_id: int,
    resource_id: int,
    session: sessionDep,
    current_user: CurrentUser,
    resource_type: ResourceType | None = Form(None),
    name: str | None = Form(None),
    quantity: int | None = Form(None, ge=0),
    category: ResourceCategory | None = Form(None),
    condition: ResourceCondition | None = Form(None),
    location: str | None = Form(None),
    purchase_date: date | None = Form(None),
    next_maintenance_date: date | None = Form(None),
    asset_number: str | None = Form(None),
    fuel_level: FuelLevel | None = Form(None),
    notes: str | None = Form(None),
    image: UploadFile | None = File(None, description="Replaces the existing image"),
):
    """
    Updates a resource. Send only the fields that changed.

    Type and category are checked against the merged result, so changing
    just one of them still has to leave a valid pairing. Uploading an
    image replaces the current one.
    """
    fields = {
        "resource_type": resource_type,
        "name": name,
        "asset_number": asset_number,
        "quantity": quantity,
        "category": category,
        "condition": condition,
        "location": location,
        "fuel_level": fuel_level,
        "purchase_date": purchase_date,
        "next_maintenance_date": next_maintenance_date,
        "notes": notes,
    }
   
    payload = _as_request(
        ResourceUpdateRequest,
        **{key: value for key, value in fields.items() if value is not None},
    )
    return update_resource(
        session, agency_id, resource_id, payload, current_user, image
    )


@resource_router.delete(
    "/agencies/{agency_id}/resources/{resource_id}", status_code=204
)
def remove_resource(
    agency_id: int,
    resource_id: int,
    session: sessionDep,
    current_user: CurrentUser,
):
    """
    Permanently removes a resource from the agency's inventory.

    Restricted to the agency's own admin. Nothing references a resource
    yet, so this cannot orphan an incident record.
    """
    delete_resource(session, agency_id, resource_id, current_user)
