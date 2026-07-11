from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import create_db_and_tables
from app.config import settings
from app.routers import auth as auth_router


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

# Routers
app.include_router(auth_router.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "env": settings.ENVIRONMENT}
