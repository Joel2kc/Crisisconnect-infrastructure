import logging
import time

from google.genai import errors, types

from ai.client import (
    AI_ENABLED,
    AI_MODEL,
    SAFETY_SETTINGS,
    AIUnavailable,
    get_client,
    guard_response,
)
from ai.contracts import IncidentTriage
from ai.prompts import TRIAGE_SYSTEM

logger = logging.getLogger(__name__)

# Below this, a call is not worth paying for - there is nothing to read.
MIN_DESCRIPTION_CHARS = 15
# Caps the cost of a single call. Descriptions this long are pathological.
MAX_DESCRIPTION_CHARS = 8000


def analyse_incident(
    description: str,
    location: str,
    reported_emergency_type: str,
    emergency_type_other: str | None = None,
) -> tuple[IncidentTriage, dict]:
    """
    Reads one incident description with Gemini.

    Returns (triage, telemetry). Raises AIUnavailable on every failure
    path so callers have exactly one exception type to handle.

    Takes plain arguments and returns a Pydantic object - this module
    never touches the database and never imports a model.
    """
    if not AI_ENABLED:
        raise AIUnavailable("AI layer is disabled by configuration.")

    text = description.strip()
    if len(text) < MIN_DESCRIPTION_CHARS:
        raise AIUnavailable("Description is too short to analyse.")
    text = text[:MAX_DESCRIPTION_CHARS]

    other = f" (free text: {emergency_type_other})" if emergency_type_other else ""

    # The description is untrusted citizen input, so it goes inside a
    # delimited block in the user turn - never concatenated into the
    # system instruction, which is what makes prompt injection possible.
    contents = (
        f"Location: {location}\n"
        f"Type selected by the citizen: {reported_emergency_type}{other}\n\n"
        f'Description:\n"""\n{text}\n"""'
    )

    started = time.perf_counter()
    try:
        response = get_client().models.generate_content(
            model=AI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=TRIAGE_SYSTEM,
                response_mime_type="application/json",
                response_schema=IncidentTriage,
                safety_settings=SAFETY_SETTINGS,
                temperature=0.2,  # classification, not prose
                thinking_config=types.ThinkingConfig(thinking_budget=512),
            ),
        )
    except errors.ClientError as exc:  # 4xx: bad key, quota, bad request
        logger.warning("triage client error: %s", exc)
        raise AIUnavailable(f"Gemini rejected the request: {exc}") from exc
    except errors.ServerError as exc:  # 5xx: transient, worth retrying
        raise AIUnavailable(f"Gemini is unavailable: {exc}") from exc
    except errors.APIError as exc:
        raise AIUnavailable(f"Gemini call failed: {exc}") from exc

    # Safety blocks and truncated generations raise here.
    guard_response(response)

    triage = response.parsed
    if triage is None:
        raise AIUnavailable("Gemini returned no parseable analysis.")

    # Gemini does not reliably enforce numeric bounds declared in the
    # schema, so clamp rather than trusting validation happened.
    triage.confidence = max(0.0, min(1.0, triage.confidence))

    usage = response.usage_metadata
    telemetry = {
        "model": AI_MODEL,
        "input_tokens": getattr(usage, "prompt_token_count", None),
        "output_tokens": getattr(usage, "candidates_token_count", None),
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
    return triage, telemetry
