from sqlmodel import Session, select, func

from db.models.incident_model import Incident, IncidentAgency
from schemas.agency_dashboard import (
    AgencyDashboardResponse,
    IncidentOverview,
    IncomingIncident,
    IncomingIncidentsResponse,
)
from enums.incident import IncidentAgencyStatus


def get_agency_dashboard(
    session: Session,
    agency_id: int,
) -> AgencyDashboardResponse:
    
    query = (
        select(Incident, IncidentAgency)
        .join(
            IncidentAgency,
            IncidentAgency.incident_id == Incident.id,
        )
        .where(
            IncidentAgency.agency_id == agency_id
        )
    )

    results = session.exec(query).all()

    # Count incidents based on this agency's status
    status_counts = {
        status: 0
        for status in IncidentAgencyStatus
    }

    for incident, incident_agency in results:
        status_counts[incident_agency.status] += 1

    # New/incoming incidents are incidents that have been
    # routed to the agency but haven't been verified yet.
    incoming_incidents = [
        IncomingIncident(
            id=incident.id,
            reference_code=incident.reference_code,
            emergency_type=incident.emergency_type,
            severity=incident.severity,
            description=incident.description,
            location=incident.location,
            status=incident_agency.status,
            occurred_at=incident.occurred_at,
        )
        for incident, incident_agency in results
        if incident_agency.status == IncidentAgencyStatus.notified
    ]

    return AgencyDashboardResponse(
        incident_overview=IncidentOverview(
            new=status_counts.get(IncidentAgencyStatus.notified, 0),
            verified=status_counts.get(IncidentAgencyStatus.verified, 0),
            assigned=0, # for now
            dispatched=status_counts.get(IncidentAgencyStatus.dispatched, 0),
            in_progress=status_counts.get(IncidentAgencyStatus.responding, 0),
            resolved=status_counts.get(IncidentAgencyStatus.resolved, 0),
        ),
        incoming_incidents=IncomingIncidentsResponse(
            data=incoming_incidents[:5],
            total=len(incoming_incidents),
        ),
    )
