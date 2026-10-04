import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlmodel import Session, select

from ai.client import AIUnavailable
from ai.triage import analyse_incident
from db.models.ai_model import IncidentAnalysis
from db.database import engine
from db.models.incident_model import Incident
from db.models.user_model import User
from enums.ai import AnalysisStatus
from enums.incident import IncidentSeverity
from services.incident_service import get_incident_detail

logger = logging.getLogger(__name__)

# The project's severity scale, ordered. Used only to decide whether
# Gemini is escalating or de-escalating what the citizen chose.
_SEVERITY_RANK = {
    IncidentSeverity.low: 0,
    IncidentSeverity.medium: 1,
    IncidentSeverity.high_critical: 2,
}


def get_analysis(session: Session, incident_id: int, actor: User) -> IncidentAnalysis:
    """
    Returns an existing analysis without paying for a new Gemini call.
    """
    # Reuses the existing authorization rules: raises 404 for a missing
    # incident and 403 for an agency user not linked to it, exactly as
    # the incident detail endpoint already does. No new permission logic
    # is written here, so no new permission bug is possible.
    get_incident_detail(session, incident_id, actor)

    analysis = session.exec(
        select(IncidentAnalysis).where(IncidentAnalysis.incident_id == incident_id)
    ).first()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This incident has not been analysed yet.",
        )
    return analysis


def run_analysis(session: Session, incident_id: int, actor: User) -> IncidentAnalysis:
    """
    Analyses an incident with Gemini and stores the result.

    Writes only to IncidentAnalysis. Never touches Incident.status,
    IncidentAgency, or any other existing table - the rollup logic in
    incident_service owns the lifecycle and stays the single source of
    truth.

    Re-running is allowed and overwrites the previous result, which is
    how a dispatcher retries after a failure.
    """
    get_incident_detail(session, incident_id, actor)  # authorize
    return _perform_analysis(session, incident_id)


def analyse_in_background(incident_id: int) -> None:
    """
    Entry point for the automatic analysis kicked off when an incident is
    reported. Runs with no actor, because there is no signed-in user to
    authorize against - a citizen reporting an emergency is frequently
    anonymous.

    Opens its own Session: the request that scheduled this has already
    returned and closed the one it was using.

    Swallows everything. A failure here must never surface anywhere near
    the citizen's report, which is already committed and safe.
    """
    try:
        with Session(engine) as session:
            _perform_analysis(session, incident_id)
    except Exception:  # noqa: BLE001 - nothing upstream can act on this
        logger.exception("background analysis failed incident=%s", incident_id)


def _perform_analysis(session: Session, incident_id: int) -> IncidentAnalysis:
    """
    The analysis itself, with no permission check of its own.

    Private on purpose. Every external caller goes through run_analysis,
    which authorizes first; the only other caller is the background task,
    which has no user to check.
    """
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found."
        )

    analysis = session.exec(
        select(IncidentAnalysis).where(IncidentAnalysis.incident_id == incident_id)
    ).first()
    if analysis is None:
        analysis = IncidentAnalysis(incident_id=incident_id)

    analysis.status = AnalysisStatus.processing
    analysis.attempts += 1
    session.add(analysis)
    session.commit()

    try:
        triage, telemetry = analyse_incident(
            description=incident.description,
            location=incident.location,
            reported_emergency_type=incident.emergency_type.value,
            emergency_type_other=incident.emergency_type_other,
        )
    except AIUnavailable as exc:
        logger.warning("triage unavailable incident=%s reason=%s", incident_id, exc)
        return _fail(session, analysis, str(exc))
    except Exception:  # noqa: BLE001 - a bug here must not 500 the dashboard
        logger.exception("triage crashed incident=%s", incident_id)
        return _fail(session, analysis, "Unexpected error during analysis.")

    analysis.summary = triage.summary
    analysis.suggested_emergency_type = triage.emergency_type
    analysis.suggested_severity = triage.severity
    analysis.key_facts = triage.key_facts
    analysis.hazards = triage.hazards
    analysis.suggested_skills = triage.suggested_skills
    analysis.recommended_agency_types = [a.value for a in triage.recommended_agency_types]
    analysis.required_resources = [r.value for r in triage.required_resources]
    analysis.confidence = triage.confidence
    analysis.needs_human_review = triage.needs_human_review

    # The disagreement flags are the actual product here. Routing keys on
    # emergency_type, so a mismatch tells a dispatcher which agency should
    # have been notified - most valuable when the citizen picked 'others',
    # which matches no AgencyCoverage row at all.
    analysis.type_disagreement = triage.emergency_type != incident.emergency_type
    # Escalation only. Never flag a de-escalation as actionable: lowering a
    # severity a person chose is not something a model should prompt.
    analysis.severity_escalation = (
        _SEVERITY_RANK[triage.severity] > _SEVERITY_RANK[incident.severity]
    )

    analysis.status = AnalysisStatus.completed
    analysis.error = None
    analysis.completed_at = datetime.utcnow()
    analysis.model = telemetry["model"]
    analysis.input_tokens = telemetry["input_tokens"]
    analysis.output_tokens = telemetry["output_tokens"]
    analysis.latency_ms = telemetry["latency_ms"]

    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def _fail(session: Session, analysis: IncidentAnalysis, reason: str) -> IncidentAnalysis:
    """
    Records a failed analysis and returns it rather than raising.

    "Analysis unavailable" is a state the dashboard renders next to the
    raw report, not an error that breaks the page. The incident itself is
    unaffected either way.
    """
    analysis.status = AnalysisStatus.failed
    analysis.error = reason[:500]
    analysis.completed_at = datetime.utcnow()
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis
