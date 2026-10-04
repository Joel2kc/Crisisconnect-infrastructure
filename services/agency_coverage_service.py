from fastapi import HTTPException, status
from sqlmodel import Session, select

from db.models.agency_model import Agency, AgencyCoverage
from db.models.user_model import User
from schemas.agency import AgencyCoverageCreate, AgencyCoverageRead


def _authorize_coverage_management(agency_id: int, actor: User) -> None:
    if actor.role.value == "crisis_connect_admin":
        return
    if actor.role.value == "agency_admin" and actor.agency_id == agency_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only your own agency's admin (or Crisis Connect Admin) can manage coverage.",
    )


def add_agency_coverage(
    session: Session, agency_id: int, payload: AgencyCoverageCreate, actor: User
) -> AgencyCoverageRead:
    agency = session.get(Agency, agency_id)
    if not agency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found.")

    _authorize_coverage_management(agency_id, actor)

    existing = session.exec(
        select(AgencyCoverage).where(
            AgencyCoverage.agency_id == agency_id,
            AgencyCoverage.emergency_type == payload.emergency_type,
        )
    ).first()

    if existing:
        if existing.active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This agency already covers this emergency type.",
            )
        # Re-activate a previously removed coverage entry instead of
        # creating a duplicate row.
        existing.active = True
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return AgencyCoverageRead.model_validate(existing)

    coverage = AgencyCoverage(agency_id=agency_id, emergency_type=payload.emergency_type)
    session.add(coverage)
    session.commit()
    session.refresh(coverage)
    return AgencyCoverageRead.model_validate(coverage)


def list_agency_coverage(session: Session, agency_id: int) -> list[AgencyCoverageRead]:
    agency = session.get(Agency, agency_id)
    if not agency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found.")

    coverage = session.exec(
        select(AgencyCoverage).where(
            AgencyCoverage.agency_id == agency_id, AgencyCoverage.active == True  # noqa: E712
        )
    ).all()
    return [AgencyCoverageRead.model_validate(c) for c in coverage]


def remove_agency_coverage(
    session: Session, agency_id: int, coverage_id: int, actor: User
) -> None:
    agency = session.get(Agency, agency_id)
    if not agency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found.")

    _authorize_coverage_management(agency_id, actor)

    coverage = session.get(AgencyCoverage, coverage_id)
    if not coverage or coverage.agency_id != agency_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coverage entry not found.")

    coverage.active = False
    session.add(coverage)
    session.commit()