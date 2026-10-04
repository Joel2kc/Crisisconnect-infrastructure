"""
Deciding whether someone has set off toward an incident, and whether they
have arrived.
"""

import math
import os

ARRIVAL_RADIUS_M = float(os.getenv("GEOFENCE_ARRIVAL_RADIUS_M", "150"))

DEPARTURE_DISTANCE_M = float(os.getenv("GEOFENCE_DEPARTURE_DISTANCE_M", "100"))

MAX_ACCEPTABLE_ACCURACY_M = float(os.getenv("GEOFENCE_MAX_ACCURACY_M", "500"))

ACCURACY_WEIGHT = float(os.getenv("GEOFENCE_ACCURACY_WEIGHT", "1"))

CONFIRMATIONS_REQUIRED = int(os.getenv("GEOFENCE_CONFIRMATIONS", "2"))

_EARTH_RADIUS_M = 6_371_000.0


def distance_metres(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Great-circle distance between two points, in metres.

    Haversine rather than a projected coordinate system: at the distances
    that matter here it is accurate to well under a metre, and it needs
    no projection that would have to be chosen per region.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def is_valid_coordinate(latitude: float | None, longitude: float | None) -> bool:
    """
    Rejects impossible coordinates and the null island bug.

    (0, 0) is in the Gulf of Guinea, several hundred kilometres off
    Nigeria. It is almost never a real fix and almost always a device
    reporting an unset location, so it is treated as missing.
    """
    if latitude is None or longitude is None:
        return False
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return False
    return not (latitude == 0 and longitude == 0)


def effective_radius(accuracy_m: float | None) -> float:
    """
    Widens the arrival radius by however uncertain the fix is.

    A device reporting 80m accuracy cannot prove it is within 150m of
    anything, so the radius it is judged against grows to match. This is
    what keeps the feature usable in dense areas instead of silently
    failing exactly where incidents cluster.
    """
    if accuracy_m is None or accuracy_m <= 0:
        return ARRIVAL_RADIUS_M
    return ARRIVAL_RADIUS_M + (
        min(accuracy_m, MAX_ACCEPTABLE_ACCURACY_M) * ACCURACY_WEIGHT
    )


def is_usable_fix(accuracy_m: float | None) -> bool:
    """A fix vaguer than MAX_ACCEPTABLE_ACCURACY_M is stored but never acted on."""
    if accuracy_m is None:
        return True
    return accuracy_m <= MAX_ACCEPTABLE_ACCURACY_M


def has_arrived(
    incident_lat: float,
    incident_lon: float,
    ping_lat: float,
    ping_lon: float,
    accuracy_m: float | None = None,
) -> bool:
    return (
        distance_metres(incident_lat, incident_lon, ping_lat, ping_lon)
        <= effective_radius(accuracy_m)
    )


def has_departed(
    origin_lat: float,
    origin_lon: float,
    ping_lat: float,
    ping_lon: float,
) -> bool:
    """
    Whether they have moved far enough from their dispatch position to
    count as travelling.

    Measured against where they were when dispatched rather than against
    the incident, because a responder already near the scene would
    otherwise never register as having set off at all.
    """
    return (
        distance_metres(origin_lat, origin_lon, ping_lat, ping_lon)
        >= DEPARTURE_DISTANCE_M
    )
