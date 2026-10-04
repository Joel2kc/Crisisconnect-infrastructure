import re

_PUNCTUATION = re.compile(r"[^a-z0-9]+")

# Words that appear in almost every Nigerian address and therefore carry
# no information about where someone actually is. Without stripping
# these, every address in the country "matches" every other one on
# 'road' or 'street'.
_STOPWORDS = {
    "street", "str", "road", "rd", "avenue", "ave", "close", "crescent",
    "drive", "lane", "way", "boulevard", "estate", "quarters", "layout",
    "phase", "block", "plot", "house", "flat", "suite", "apartment",
    "off", "opposite", "beside", "near", "behind", "front", "junction",
    "roundabout", "bus", "stop", "garage", "market", "area", "axis",
    "state", "nigeria", "local", "government", "lga", "no", "number",
    "and", "the", "of", "at", "by",
}


def location_terms(text: str | None) -> set[str]:
    """
    The place-name tokens in an address.

    Drops generic address furniture, pure numbers, and anything under
    three characters, leaving the parts that actually identify a place.
    """
    if not text:
        return set()

    tokens = _PUNCTUATION.sub(" ", text.lower()).split()
    return {
        token
        for token in tokens
        if len(token) >= 3 and token not in _STOPWORDS and not token.isdigit()
    }


def shared_terms(incident_location: str | None, address: str | None) -> list[str]:
    """
    Place names common to both, sorted so the result is stable.

    More shared terms is a stronger signal: matching on 'ikeja' and
    'allen' says more than matching on 'lagos' alone, which half the
    country would match.
    """
    return sorted(location_terms(incident_location) & location_terms(address))
