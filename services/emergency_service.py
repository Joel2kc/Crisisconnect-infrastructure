from datetime import datetime

from fastapi import HTTPException, status
from sqlmodel import Session, select

from db.models.emergency_categories import EmergencyCategory
from db.models.emergency_contact import EmergencyContact
from schemas.emergency import (
    EmergencyCategoryCreate,
    EmergencyCategoryUpdate,
    EmergencyCategoryWithContacts,
    EmergencyContactCreate,
    EmergencyContactRead,
    EmergencyContactUpdate,
)


def _get_category_or_404(session: Session, category_id: int) -> EmergencyCategory:
    category = session.get(EmergencyCategory, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency category not found.",
        )
    return category


def create_category(
    session: Session,
    payload: EmergencyCategoryCreate,
) -> EmergencyCategory:
    existing = session.exec(
        select(EmergencyCategory).where(EmergencyCategory.name == payload.name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists.",
        )

    category = EmergencyCategory(
        name=payload.name,
        description=payload.description,
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def update_category(
    session: Session,
    category_id: int,
    payload: EmergencyCategoryUpdate,
) -> EmergencyCategory:
    category = _get_category_or_404(session, category_id)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update.",
        )

    # Uniqueness check if the name is being changed
    if "name" in update_data and update_data["name"] != category.name:
        duplicate = session.exec(
            select(EmergencyCategory).where(
                EmergencyCategory.name == update_data["name"]
            )
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with this name already exists.",
            )

    for field, value in update_data.items():
        setattr(category, field, value)

    category.updated_at = datetime.utcnow()
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def deactivate_category(
    session: Session,
    category_id: int,
) -> EmergencyCategory:
    category = _get_category_or_404(session, category_id)

    if not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category is already deactivated.",
        )

    category.is_active = False
    category.updated_at = datetime.utcnow()
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def get_categories(session: Session) -> list[EmergencyCategory]:
    """Returns all categories (both active and inactive) for admin use."""
    return list(
        session.exec(
            select(EmergencyCategory).order_by(EmergencyCategory.name)
        ).all()
    )


def _get_contact_or_404(session: Session, contact_id: int) -> EmergencyContact:
    contact = session.get(EmergencyContact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency contact not found.",
        )
    return contact


def _validate_category_exists(session: Session, category_id: int) -> None:
    category = session.get(EmergencyCategory, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Emergency category with id {category_id} does not exist.",
        )


def create_contact(
    session: Session,
    payload: EmergencyContactCreate,
) -> EmergencyContact:
    _validate_category_exists(session, payload.category_id)

    existing = session.exec(
        select(EmergencyContact).where(
            EmergencyContact.phone_number == payload.phone_number
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A contact with this phone number already exists.",
        )

    contact = EmergencyContact(
        name=payload.name,
        phone_number=payload.phone_number,
        location=payload.location,
        category_id=payload.category_id,
    )
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def update_contact(
    session: Session,
    contact_id: int,
    payload: EmergencyContactUpdate,
) -> EmergencyContact:
    contact = _get_contact_or_404(session, contact_id)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update.",
        )

    # Validate FK if category_id is being changed
    if "category_id" in update_data:
        _validate_category_exists(session, update_data["category_id"])

    # Uniqueness check if phone number is being changed
    if "phone_number" in update_data and update_data["phone_number"] != contact.phone_number:
        duplicate = session.exec(
            select(EmergencyContact).where(
                EmergencyContact.phone_number == update_data["phone_number"]
            )
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A contact with this phone number already exists.",
            )

    for field, value in update_data.items():
        setattr(contact, field, value)

    contact.updated_at = datetime.utcnow()
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def deactivate_contact(
    session: Session,
    contact_id: int,
) -> EmergencyContact:
    contact = _get_contact_or_404(session, contact_id)

    if not contact.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact is already deactivated.",
        )

    contact.is_active = False
    contact.updated_at = datetime.utcnow()
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def get_contacts_by_category(
    session: Session,
    category_name: str | None = None,
) -> list[EmergencyCategoryWithContacts]:
    """
    Public lookup. Returns active categories, each with their active
    contacts nested inside. Optionally filtered to a single category.
    """
    query = select(EmergencyCategory).where(EmergencyCategory.is_active == True)

    if category_name is not None:
        query = query.where(EmergencyCategory.name == category_name)

    categories = session.exec(query.order_by(EmergencyCategory.name)).all()

    results: list[EmergencyCategoryWithContacts] = []
    for cat in categories:
        contacts = session.exec(
            select(EmergencyContact).where(
                EmergencyContact.category_id == cat.id,
                EmergencyContact.is_active == True,
            )
        ).all()

        results.append(
            EmergencyCategoryWithContacts(
                id=cat.id,
                name=cat.name,
                description=cat.description,
                is_active=cat.is_active,
                created_at=cat.created_at,
                updated_at=cat.updated_at,
                contacts=[
                    EmergencyContactRead.model_validate(c) for c in contacts
                ],
            )
        )

    return results
