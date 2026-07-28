"""
Aced API — University Tutoring Platform
========================================
FastAPI application with:
- Sentry error tracking [E008-S05]
- Structured JSON logging with correlation IDs [E008-S05]
- Rate limiting via SlowAPI [E008-S02]
- JWT authentication with rotating refresh tokens [E001-S02]
- CORS support for frontend integration

Interactive docs: /docs (Swagger UI) or /redoc (ReDoc)
Health check: GET /health
"""

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import create_db_and_tables
from app.config import settings
from app.logging_config import setup_logging, CorrelationIDMiddleware, get_logger
from app.rate_limit import limiter

# Import routers
from app.routers import auth as auth_router
from app.routers import tutors as tutors_router
from app.routers import media as media_router
from app.routers import bookings as bookings_router
from app.routers import payments as payments_router
from app.routers import admin as admin_router
from app.routers import public as public_router

logger = get_logger("aced.main")


# ── Sentry Initialization [E008-S05] ──────────────────────────────────────────

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "production" else 0.0,
        send_default_pii=False,  # NDPR compliance — don't send PII
    )
    logger.info("Sentry initialized for environment: %s", settings.ENVIRONMENT)
else:
    logger.info("Sentry not configured — skipping initialization")


# ── Application Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("Starting Aced API...")
    create_db_and_tables()
    logger.info("Database tables created/verified")
    yield
    # Shutdown
    logger.info("Shutting down Aced API...")


# ── Application Factory ───────────────────────────────────────────────────────

app = FastAPI(
    title="Aced API",
    description="""
    **University Tutoring Platform** — Connect students with verified tutors.

    ## Features
    * 🔐 **Dual-Role Auth** — Students & Tutors with JWT + rotating refresh tokens
    * 👨‍🏫 **Tutor Discovery** — Search by course code, price (₦1,000–₦5,000), and ratings
    * 💳 **Escrow Payments** — Paystack integration with rigid state machine
    * ✅ **Verified A** — Manual grade verification as the primary trust marker
    * 📱 **WhatsApp Reminders** — Session reminders 24h and 1h before
    * 🛡️ **Rate Limited** — 5 login attempts/15min, 100 global requests/min

    ## Security
    * Stateless JWT (15min access tokens, 7-day rotating refresh tokens)
    * All inputs validated with Pydantic schemas
    * Rate limiting via SlowAPI
    * Sentry error tracking (500-series alerts)
    * CORS restricted in production

    ## Endpoint Prefixes
    | Prefix       | Description              |
    |--------------|--------------------------|
    | `/auth`      | Register, Login, Refresh |
    | `/tutors`    | Search & Profiles        |
    | `/media`     | Video & Matric ID Upload |
    | `/bookings`  | Session Booking & States |
    | `/payments`  | Paystack Integration     |
    | `/admin`     | Verification & Ledger    |
    | `/public`    | Public Tutor Profiles    |
    """,
    version="0.1.0",
    lifespan=lifespan,

    # Enhanced Swagger UI [E008-S04]
    swagger_ui_parameters={
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
        "syntaxHighlight.theme": "monokai",
    },
    license_info={
        "name": "MIT",
        "identifier": "MIT",
    },
    contact={
        "name": "Aced Team",
        "url": "https://aced.com",
    },
)

# ── Middleware ─────────────────────────────────────────────────────────────────

# CORS — allow frontend origin
origins = ["http://localhost:3000", "https://aced.com"]
if settings.ENVIRONMENT == "development":
    origins.append("*")  # Allow all origins in dev

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured JSON logging with correlation IDs
app.add_middleware(CorrelationIDMiddleware)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router.router)
app.include_router(tutors_router.router)
app.include_router(media_router.router)
app.include_router(bookings_router.router)
app.include_router(payments_router.router)
app.include_router(admin_router.router)
app.include_router(public_router.router)

# Setup structured logging on startup
setup_logging()


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
@limiter.limit("100/minute")
def health_check(request: Request):
    """Health check endpoint. Returns the application status and environment."""
    return {
        "status": "ok",
        "env": settings.ENVIRONMENT,
        "version": "0.1.0",
    }
