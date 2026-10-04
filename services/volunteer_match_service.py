"""
Suggests volunteers for an incident from its stored AI analysis.

Read-only by design. This module runs SELECTs and nothing else: it
creates no rows, updates no rows, and needs no new table. There is
currently nowhere in the schema to record a volunteer assignment
(incident_model.py has IncidentAgency but no volunteer equivalent), so
the output is a ranked shortlist a dispatcher acts on out-of-band.

The ranking is deliberately deterministic rather than a second Gemini
call. Ordering people who already matched on skills adds little that a
score cannot express, and paying for a model call - plus owning its
timeout and failure paths - on a plain listing endpoint is not a trade
worth making. Gemini's contribution here is upstream: it is what turned
a free-text emergency report into the skill names this module resolves.
"""

import re

from sqlmodel import Session, select

from db.models.incident_model import Incident
from db.models.user_model import User
from db.models.volunteer_model import Skill, VolunteerProfile, VolunteerSkill
from enums.ai import AnalysisStatus
from enums.incident import IncidentSeverity
from enums.volunteer import AvailabilityStatus
from schemas.ai import VolunteerMatch, VolunteerSuggestionResponse
from services.ai_service import get_analysis

_PUNCTUATION = re.compile(r"[^a-z0-9]+")


def _normalise(name: str) -> str:
    """
    Reduces a skill name to a comparable key.

    The two vocabularies genuinely differ: scripts/seed_skills.py stores
    "Search & Rescue" while the model is asked for short lowercase names
    and returns "search and rescue". Lowercasing alone does not bridge
    that, so '&' is spelled out and punctuation is flattened.
    """
    return _PUNCTUATION.sub(" ", name.lower().replace("&", " and ")).strip()


def _is_available(profile: VolunteerProfile, incident: Incident) -> bool:
    """
    Whether a volunteer's stated availability covers this incident.

    A life-threatening incident ignores the schedule entirely - deciding
    who to actually call is the dispatcher's job, and silently hiding a
    qualified person from that decision is the worse error.
    """
    if incident.severity == IncidentSeverity.high_critical:
        return True

    statuses = set(profile.availability_status or [])
    if AvailabilityStatus.emergencies_only in statuses:
        return True

    weekend = incident.occurred_at.weekday() >= 5
    wanted = AvailabilityStatus.weekends if weekend else AvailabilityStatus.weekdays
    return wanted in statuses


def suggest_volunteers(
    session: Session,
    incident_id: int,
    actor: User,
    limit: int = 25,
    include_unavailable: bool = False,
) -> VolunteerSuggestionResponse:
    # Authorization and existence checks are inherited: get_analysis calls
    # get_incident_detail, which raises 404 for a missing incident and 403
    # for an agency user not linked to it. No new permission logic here.
    analysis = get_analysis(session, incident_id, actor)
    incident = session.get(Incident, incident_id)

    response = VolunteerSuggestionResponse(
        incident_id=incident_id,
        suggested_skills=analysis.suggested_skills or [],
        resolved_skills=[],
        unmatched_skills=[],
        matches=[],
    )

    if analysis.status != AnalysisStatus.completed:
        # Rendered by the dashboard as "no suggestions yet" rather than an
        # error, so an incomplete analysis does not break the panel.
        response.reason = (
            f"Analysis is '{analysis.status.value}', not completed. "
            "Run the analysis first."
        )
        return response

    if not analysis.suggested_skills:
        response.reason = "The analysis did not identify any volunteer skills."
        return response

    # 1. Resolve the model's skill names against real Skill rows.
    #
    # Loaded whole and matched in Python rather than one ilike query per
    # name: the table is small, volunteers can mint new rows at
    # registration (volunteer_service.py), and the '&'/'and' problem needs
    # normalisation on both sides anyway. Anything that fails to resolve is
    # dropped - a skill with no row can match no volunteer.
    all_skills = session.exec(select(Skill)).all()
    by_key: dict[str, list[Skill]] = {}
    for skill in all_skills:
        by_key.setdefault(_normalise(skill.name), []).append(skill)

    skill_names: dict[int, str] = {}

    for suggested in analysis.suggested_skills:
        found = by_key.get(_normalise(suggested))
        if not found:
            response.unmatched_skills.append(suggested)
            continue
        for skill in found:
            skill_names[skill.id] = skill.name
        response.resolved_skills.append(suggested)

    if not skill_names:
        response.reason = (
            "None of the suggested skills exist in the skills table. "
            "Seed them, or register volunteers who hold them."
        )
        return response

    # 2. Everyone holding at least one of those skills.
    links = session.exec(
        select(VolunteerSkill).where(VolunteerSkill.skill_id.in_(list(skill_names)))
    ).all()

    matched_by_volunteer: dict[int, list[str]] = {}
    for link in links:
        matched_by_volunteer.setdefault(link.volunteer_id, []).append(
            skill_names[link.skill_id]
        )

    if not matched_by_volunteer:
        response.reason = "No volunteer currently holds any of the suggested skills."
        return response

    profiles = session.exec(
        select(VolunteerProfile).where(
            VolunteerProfile.id.in_(list(matched_by_volunteer))
        )
    ).all()

    users = {
        user.id: user
        for user in session.exec(
            select(User).where(User.id.in_([p.user_id for p in profiles]))
        ).all()
    }

    # 3. Filter and rank. Availability is applied in Python rather than as
    # a Postgres array overlap, keeping the enum-array comparison simple.
    filtered_out = 0

    for profile in profiles:
        user = users.get(profile.user_id)
        if not user or not user.is_active:
            continue
        # verified is the platform's own quality gate on a volunteer. An
        # unverified profile is a stranger who filled in a form.
        if not profile.verified:
            filtered_out += 1
            continue
        if not include_unavailable and not _is_available(profile, incident):
            filtered_out += 1
            continue

        skills = sorted(matched_by_volunteer[profile.id])
        response.matches.append(
            VolunteerMatch(
                volunteer_id=profile.id,
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone,
                matched_skills=skills,
                matched_skill_count=len(skills),
                availability_status=list(profile.availability_status or []),
                certifications=profile.certifications,
            )
        )

    # Most skills first; the lower volunteer id breaks the tie, which keeps
    # the order stable between calls.
    response.matches.sort(key=lambda m: (-m.matched_skill_count, m.volunteer_id))
    del response.matches[limit:]

    if not response.matches:
        response.reason = (
            f"{filtered_out} volunteer(s) matched on skills but none were "
            "verified and available. Retry with include_unavailable=true to "
            "see them."
        )
    return response
