import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    ai,
    appointments,
    auth,
    doctor_availability,
    doctor_availability_slots,
    doctor_leave,
    doctors,
    notifications,
    waitlist,
)
from app.core.config import settings
from app.middleware.rate_limiting import RateLimitingMiddleware

logging.basicConfig(level=logging.INFO)

# Fail fast rather than silently running with insecure defaults in production.
settings.validate_production_safety()

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# Add rate limiting middleware
app.add_middleware(RateLimitingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(doctor_availability.router)
app.include_router(doctor_leave.router)
app.include_router(doctor_availability_slots.router)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(ai.router)
app.include_router(waitlist.router)
app.include_router(notifications.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}
