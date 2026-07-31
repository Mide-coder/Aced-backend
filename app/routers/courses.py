"""Courses Router — public course listing used by admin & booking pages."""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Course

router = APIRouter(tags=["Courses"])


@router.get("/courses", response_model=list[Course])
def list_courses(session: Session = Depends(get_session)):
    """List all courses ordered by code. Public — used by admin & booking pages."""
    return session.exec(select(Course).order_by(Course.code)).all()
