from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import create_db_and_tables
from app.config import settings
from app.routers import auth as auth_router
from app.routers import tutors as tutors_router
from app.routers import media as media_router
from app.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_db_and_tables()
    yield
    # Shutdown


app = FastAPI(
    title="Aced API",
    description="University Tutoring Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Routers
app.include_router(auth_router.router)
app.include_router(tutors_router.router)
app.include_router(media_router.router)


@app.get("/health")
@limiter.limit("100/minute")  # Global rate limit
def health_check(request: Request):
    return {"status": "ok", "env": settings.ENVIRONMENT}
