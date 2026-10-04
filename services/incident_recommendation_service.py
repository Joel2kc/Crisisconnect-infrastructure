import logging
import re

from sqlmodel import Session, select

from db.models.agency_model import Agency, AgencyCoverage
from db.models.ai_model import IncidentAnalysis
from db.models.incident_model import Incident, IncidentAgency
from db.models.resource_model import AgencyResource
from db.models.responder_model import (
    ResponderAssignment,
    ResponderProfile,
    ResponderSkill,
)
from db.models.user_model import User
from db.models.volunteer_assignment_model import IncidentVolunteer
from db.models.volunteer_model import Skill, VolunteerProfile, VolunteerSkill
from enums.agency import AgencyType, AgencyVerificationStatus
from enums.ai import AnalysisStatus
from enums.incident import IncidentSeverity
from enums.resource import ResourceCondition, ResourceType
from enums.responder import ResponderAssignmentStatus, ResponderAvailabilityStatus
from enums.user import UserRole
from enums.volunteer import AvailabilityStatus
from enums.volunteer_assignment import VolunteerAssignmentStatus
from schemas.ai import (
    AgencySuggestion,
    IncidentRecommendations,
    ResourceMatch,
    ResourceRequirement,
    ResponderMatch,
    RoutingRecommendation,
    VolunteerMatch,
)
from services.ai_service import get_analysis
from services.location_match import shared_terms

logger = logging.getLogger(__name__)

_PUNCTUATION = re.compile(r"[^a-z0-9]+")

# Worst condition first would bury the usable kit, so rank it.
_CONDITION_RANK = {
    ResourceCondition.good: 0,
    ResourceCondition.fair: 1,
    ResourceCondition.poor: 2,
}

_AGENCY_SCOPED_ROLES = {
    UserRole.agency_admin,
    UserRole.agency_dispatcher,
    UserRole.responder,
}


def _normalise(name: str) -> str:
    """
    Reduces a skill name to a comparable key.

    seed_skills.py stores "Search & Rescue"; the model is asked for short
    lowercase names and returns "search and rescue". Lowercasing alone
    does not bridge that, so '&' is spelled out and punctuation flattened.
    """
    return _PUNCTUATION.sub(" ", name.lower().replace("&", " and ")).strip()


def _resolve_skills(
    session: Session, suggested: list[str]
) -> tuple[dict[int, str], list[str], list[str]]:
    """
    Maps the model's skill names onto real Skill rows.

    Returns (skill id -> canonical name, resolved names, unmatched names).
    Anything that fails to resolve is dropped: a skill with no row can
    match no one. The unmatched list is reported back because it is the
    signal that the skills table needs seeding.
    """
    by_key: dict[str, list[Skill]] = {}
    for skill in session.exec(select(Skill)).all():
        by_key.setdefault(_normalise(skill.name), []).append(skill)

    skill_names: dict[int, str] = {}
    resolved: list[str] = []
    unmatched: list[str] = []

    for name in suggested:
        found = by_key.get(_normalise(name))
        if not found:
            unmatched.append(name)
            continue
        for skill in found:
            skill_names[skill.id] = skill.name
        resolved.append(name)

    return skill_names, resolved, unmatched


def _resolve_agency_scope(
    session: Session, incident: Incident, actor: User, agency_id: int | None
) -> int | None:
    """
    Works out whose responders and resources to show.

    Agency staff always see their own, whatever they ask for - the point
    of the panel is what *this* agency can send. Cross-agency roles pick
    with the agency_id parameter, defaulting to the incident's primary
    agency so the common case needs no argument.
    """
    if actor.role in _AGENCY_SCOPED_ROLES:
        return actor.agency_id

    if agency_id is not None:
        return agency_id

    primary = session.exec(
        select(IncidentAgency)
        .where(IncidentAgency.incident_id == incident.id)
        .order_by(IncidentAgency.id)
    ).first()
    return primary.agency_id if primary else None


def _routing(
    session: Session, incident: Incident, analysis: IncidentAnalysis
) -> tuple[RoutingRecommendation, list[AgencySuggestion]]:
    """
    Says whether the incident reached the right agencies, and who else
    should be on it.

    Two independent sources of suggestion:

    1. A type disagreement. Routing matches AgencyCoverage on
       emergency_type, so if the citizen filed 'others' - which no
       coverage row matches - the incident reached nobody at all. The
       agencies covering the type Gemini read is the concrete fix, and
       this is the highest-value recommendation in the whole flow.
    2. The agency types Gemini named. Coverage routing sends an incident
       to whoever covers one emergency type; it cannot express "this
       needs fire, medical and police together".
    """
    routed_ids = {
        link.agency_id
        for link in session.exec(
            select(IncidentAgency).where(IncidentAgency.incident_id == incident.id)
        ).all()
    }

    suggestions: dict[int, AgencySuggestion] = {}

    def add(agency: Agency, reason: str) -> None:
        if agency.id in routed_ids or agency.id in suggestions:
            return
        suggestions[agency.id] = AgencySuggestion(
            agency_id=agency.id,
            name=agency.name,
            type=agency.type,
            region=agency.region,
            reason=reason,
        )

    suggested_type = analysis.suggested_emergency_type
    if analysis.type_disagreement and suggested_type is not None:
        covering = session.exec(
            select(Agency)
            .join(AgencyCoverage, AgencyCoverage.agency_id == Agency.id)
            .where(
                AgencyCoverage.emergency_type == suggested_type,
                AgencyCoverage.active == True,  # noqa: E712 - SQL, not Python
                Agency.verification_status == AgencyVerificationStatus.verified,
            )
        ).all()
        for agency in covering:
            add(agency, f"covers '{suggested_type.value}', the type the AI read")

    recommended_types = []
    for value in analysis.recommended_agency_types or []:
        try:
            recommended_types.append(AgencyType(value))
        except ValueError:
            # An agency type retired since the analysis was stored.
            logger.warning("unknown agency type in analysis: %s", value)

    if recommended_types:
        for agency in session.exec(
            select(Agency).where(
                Agency.type.in_(recommended_types),
                Agency.verification_status == AgencyVerificationStatus.verified,
            )
        ).all():
            add(agency, f"AI recommended {agency.type.value} for this incident")

    routing = RoutingRecommendation(
        reported_emergency_type=incident.emergency_type,
        suggested_emergency_type=suggested_type,
        type_disagreement=analysis.type_disagreement,
        severity_escalation=analysis.severity_escalation,
        routed_agency_ids=sorted(routed_ids),
        reaches_no_agency=not routed_ids,
    )
    return routing, list(suggestions.values())


def _responders(
    session: Session,
    incident: Incident,
    agency_id: int | None,
    skill_names: dict[int, str],
    limit: int,
) -> list[ResponderMatch]:
    """
    The agency's own responders, best skill match first.

    Unlike volunteers, responders with no matching skill are still
    included: they are staff on shift, and a dispatcher would rather see
    the whole available roster ranked than a filtered subset. Ordering
    carries the recommendation, not membership of the list.
    """
    if agency_id is None:
        return []

    rows = session.exec(
        select(ResponderProfile, User)
        .join(User, User.id == ResponderProfile.user_id)
        .where(User.agency_id == agency_id, User.is_active == True)  # noqa: E712
    ).all()
    if not rows:
        return []

    profile_ids = [profile.id for profile, _ in rows]

    matched: dict[int, list[str]] = {}
    if skill_names:
        for link in session.exec(
            select(ResponderSkill).where(
                ResponderSkill.responder_id.in_(profile_ids),
                ResponderSkill.skill_id.in_(list(skill_names)),
            )
        ).all():
            matched.setdefault(link.responder_id, []).append(
                skill_names[link.skill_id]
            )

    # Someone already on this incident is not a recommendation.
    already_assigned = {
        assignment.responder_id
        for assignment in session.exec(
            select(ResponderAssignment).where(
                ResponderAssignment.incident_id == incident.id,
                ResponderAssignment.status != ResponderAssignmentStatus.complete,
            )
        ).all()
    }

    matches = []
    for profile, user in rows:
        if profile.id in already_assigned:
            continue
        skills = sorted(matched.get(profile.id, []))
        matches.append(
            ResponderMatch(
                responder_id=profile.id,
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone,
                position=profile.position,
                employee_id=profile.employee_id,
                availability_status=profile.availability_status,
                matched_skills=skills,
                matched_skill_count=len(skills),
            )
        )

    # Available first, then most matching skills. A responder already out
    # on another call should not head the list however well they match.
    matches.sort(
        key=lambda m: (
            m.availability_status != ResponderAvailabilityStatus.available,
            -m.matched_skill_count,
            m.responder_id,
        )
    )
    return matches[:limit]


def _volunteers(
    session: Session,
    incident: Incident,
    skill_names: dict[int, str],
    limit: int,
    near_only: bool = False,
) -> list[VolunteerMatch]:
    """
    Verified volunteers holding at least one suggested skill.

    Stricter than the responder list in both directions: a volunteer with
    no matching skill is not a candidate at all, and availability is a
    filter rather than a sort key. Volunteers are members of the public,
    not staff on shift.
    """
    if not skill_names:
        return []

    links = session.exec(
        select(VolunteerSkill).where(VolunteerSkill.skill_id.in_(list(skill_names)))
    ).all()
    if not links:
        return []

    matched: dict[int, list[str]] = {}
    for link in links:
        matched.setdefault(link.volunteer_id, []).append(skill_names[link.skill_id])

    profiles = session.exec(
        select(VolunteerProfile).where(VolunteerProfile.id.in_(list(matched)))
    ).all()
    users = {
        user.id: user
        for user in session.exec(
            select(User).where(User.id.in_([p.user_id for p in profiles]))
        ).all()
    }

    weekend = incident.occurred_at.weekday() >= 5
    wanted = AvailabilityStatus.weekends if weekend else AvailabilityStatus.weekdays

    # Someone already invited to this incident is not a recommendation -
    # whether they are still deciding or have already said yes.
    already_invited = {
        invitation.volunteer_id
        for invitation in session.exec(
            select(IncidentVolunteer).where(
                IncidentVolunteer.incident_id == incident.id,
                IncidentVolunteer.status.in_(
                    [
                        VolunteerAssignmentStatus.invited,
                        VolunteerAssignmentStatus.accepted,
                    ]
                ),
            )
        ).all()
    }

    matches = []
    for profile in profiles:
        if profile.id in already_invited:
            continue
        user = users.get(profile.user_id)
        if not user or not user.is_active or not profile.verified:
            continue

        statuses = set(profile.availability_status or [])
        available = (
            # A life-threatening incident ignores the roster. Hiding a
            # qualified person from that decision is the worse error.
            incident.severity == IncidentSeverity.high_critical
            or AvailabilityStatus.emergencies_only in statuses
            or wanted in statuses
        )
        if not available:
            continue

        shared = shared_terms(incident.location, profile.address)
        if near_only and not shared:
            continue

        skills = sorted(matched[profile.id])
        matches.append(
            VolunteerMatch(
                volunteer_id=profile.id,
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone,
                matched_skills=skills,
                matched_skill_count=len(skills),
                availability_status=list(statuses),
                certifications=profile.certifications,
                address=profile.address,
                matched_location_terms=shared,
                location_match=bool(shared),
            )
        )

    # Skills first, then location. Deliberately that order: the location
    # signal is a string overlap between two free-text addresses, so it
    # is far weaker evidence than a registered skill. It breaks ties
    # between equally qualified volunteers rather than outranking
    # qualification, and a dispatcher wanting the opposite can pass
    # near_incident_only.
    matches.sort(
        key=lambda m: (
            -m.matched_skill_count,
            -len(m.matched_location_terms),
            m.volunteer_id,
        )
    )
    return matches[:limit]


def _resources(
    session: Session, analysis: IncidentAnalysis, agency_id: int | None
) -> list[ResourceRequirement]:
    """
    What the incident calls for, against what the agency actually holds.

    The gaps are the point. "No water tanker on the register" is what
    tells a dispatcher to call a neighbouring agency, and it is the one
    thing a model reasoning from the description alone can never say.
    """
    requirements = []

    for value in analysis.required_resources or []:
        try:
            resource_type = ResourceType(value)
        except ValueError:
            logger.warning("unknown resource type in analysis: %s", value)
            continue

        available = []
        if agency_id is not None:
            rows = session.exec(
                select(AgencyResource).where(
                    AgencyResource.agency_id == agency_id,
                    AgencyResource.resource_type == resource_type,
                    AgencyResource.quantity > 0,
                )
            ).all()
            # Serviceable kit first; a 'poor' item is still listed, because
            # a dispatcher with nothing else needs to know it exists.
            rows.sort(key=lambda r: (_CONDITION_RANK[r.condition], r.name))
            available = [
                ResourceMatch(
                    resource_id=row.id,
                    name=row.name,
                    asset_number=row.asset_number,
                    category=row.category,
                    condition=row.condition,
                    quantity=row.quantity,
                    location=row.location,
                    fuel_level=row.fuel_level,
                    last_updated=row.updated_at,
                )
                for row in rows
            ]

        requirements.append(
            ResourceRequirement(
                resource_type=resource_type,
                available=available,
                available_count=sum(item.quantity for item in available),
                # Nothing on the register that matches. Rendered as a gap,
                # never as an empty section.
                #
                # False when there is no agency in scope: nothing was
                # checked, and reporting an unchecked gap as a real one
                # would send a dispatcher chasing equipment that may well
                # be sitting in the station.
                missing=agency_id is not None and not available,
            )
        )

    return requirements


def recommend_for_incident(
    session: Session,
    incident_id: int,
    actor: User,
    agency_id: int | None = None,
    responder_limit: int = 25,
    volunteer_limit: int = 25,
    near_incident_only: bool = False,
) -> IncidentRecommendations:
    """
    The full recommendation panel for one incident.

    A read. It costs nothing, calls no model, and is safe to poll - the
    Gemini call already happened when the incident was analysed.
    """
   
    analysis = get_analysis(session, incident_id, actor)
    incident = session.get(Incident, incident_id)

    scoped_agency_id = _resolve_agency_scope(session, incident, actor, agency_id)

    if analysis.status != AnalysisStatus.completed:
        return IncidentRecommendations(
            incident_id=incident_id,
            agency_id=scoped_agency_id,
            analysis_status=analysis.status,
            routing=RoutingRecommendation(
                reported_emergency_type=incident.emergency_type,
                suggested_emergency_type=None,
                type_disagreement=False,
                severity_escalation=False,
                routed_agency_ids=[],
                reaches_no_agency=False,
            ),
            reason=(
                f"Analysis is '{analysis.status.value}', not completed. "
                "Recommendations become available once it succeeds."
            ),
        )

    skill_names, resolved, unmatched = _resolve_skills(
        session, analysis.suggested_skills or []
    )
    routing, agency_suggestions = _routing(session, incident, analysis)

    return IncidentRecommendations(
        incident_id=incident_id,
        agency_id=scoped_agency_id,
        analysis_status=analysis.status,
        summary=analysis.summary,
        hazards=analysis.hazards or [],
        routing=routing,
        suggested_agencies=agency_suggestions,
        responders=_responders(
            session, incident, scoped_agency_id, skill_names, responder_limit
        ),
        volunteers=_volunteers(
            session, incident, skill_names, volunteer_limit, near_incident_only
        ),
        resources=_resources(session, analysis, scoped_agency_id),
        suggested_skills=analysis.suggested_skills or [],
        resolved_skills=resolved,
        unmatched_skills=unmatched,
        reason=(
            "No agency in scope - responders and resources cannot be listed."
            if scoped_agency_id is None
            else None
        ),
    )
