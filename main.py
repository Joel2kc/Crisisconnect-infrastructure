from fastapi import FastAPI

# limiter imports below
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from rate_limiter.rate_limiter import limiter

from api.v1 import (
    admin,
    agency,
    ai,
    default,
    emergency,
    incidents,
    location,
    resource,
    responder_assignment,
    users,
    volunteer,
    volunteer_assignment,
    responder,
)

app = FastAPI(title="CrisisConnect API")

# rate limiter setup below
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(users.user_router)
app.include_router(agency.agency_router)
app.include_router(volunteer.volunteer_router)
app.include_router(incidents.incident_router)
app.include_router(ai.ai_router)
app.include_router(location.location_router)
app.include_router(resource.resource_router)
app.include_router(responder.responder_router)
app.include_router(responder_assignment.responder_assignment_router)
app.include_router(volunteer_assignment.incident_volunteer_router)
app.include_router(volunteer_assignment.volunteer_dashboard_router)
app.include_router(emergency.emergency_router)
app.include_router(admin.admin_router)
app.include_router(default.home_route)
