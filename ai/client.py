import os
from functools import lru_cache

from google import genai
from google.genai import types

# Read at module level, matching how the rest of the codebase handles
# config (see file_storage_service.py and core/dependencies.py).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "gemini-3.6-flash")
AI_ENABLED = os.getenv("AI_ENABLED", "true").lower() == "true"
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "60"))


class AIUnavailable(RuntimeError):
    """
    Analysis could not be produced.

    Always non-fatal: an incident is a perfectly valid incident without
    an analysis attached. Callers record the reason and carry on.
    """


# Emergency reports describe death, fire, injury and violence. Gemini's
# default safety thresholds block exactly that content, which would make
# the platform fail hardest on its most severe incidents - the inverse of
# what an emergency system must do. Relax them explicitly.
#
# If BLOCK_NONE is rejected on your API tier, fall back to
# BLOCK_ONLY_HIGH, which is still far more permissive than the default.
SAFETY_SETTINGS = [
    types.SafetySetting(
        category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"
    ),
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
    types.SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"
    ),
]


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise AIUnavailable("GEMINI_API_KEY is not configured.")

    return genai.Client(
        api_key=GEMINI_API_KEY,
        # NOTE: timeout is in MILLISECONDS in google-genai, not seconds.
        http_options=types.HttpOptions(timeout=int(AI_TIMEOUT_SECONDS * 1000)),
    )


def guard_response(response) -> None:
    """
    Raises AIUnavailable unless the model actually finished normally.

    A safety block or a truncated generation must never be mistaken for
    an empty-but-valid analysis, because a blank analysis panel reads to
    a dispatcher as "nothing serious here".
    """
    feedback = getattr(response, "prompt_feedback", None)
    if feedback and getattr(feedback, "block_reason", None):
        raise AIUnavailable(f"Prompt blocked by safety filter: {feedback.block_reason}")

    if not response.candidates:
        raise AIUnavailable("Model returned no candidates.")

    finish = str(response.candidates[0].finish_reason or "")
    # STOP is the only success. SAFETY, MAX_TOKENS and RECITATION are not.
    if "STOP" not in finish.upper():
        raise AIUnavailable(f"Generation stopped early: {finish}")
