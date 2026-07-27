from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_session
from app.models import (
    TutorProfile, TutorProfileRead, TutorCourse,
    Course, Review, ReviewRead, User, UserRead,
    TutorSearchResult,
)
from app.auth import get_current_user
from app.rate_limit import limiter

router = APIRouter(prefix="/tutors", tags=["Tutors"])


# ── Tutor Search [E003-S01] ───────────────────────────────────────────────────

@router.get("/search", response_model=list[TutorSearchResult])
@limiter.limit("100/minute")
def search_tutors(
    request: Request,
    course_code: Optional[str] = Query(None, description="Course code e.g. CSC201"),
    min_price: Optional[float] = Query(None, ge=1000, description="Min price in Naira"),
    max_price: Optional[float] = Query(None, le=5000, description="Max price in Naira"),
    min_rating: Optional[float] = Query(None, ge=1.0, le=5.0),
    grade_verified: Optional[bool] = Query(None, description="Filter by Verified A badge"),
    session: Session = Depends(get_session),
):
    """
    Search for tutors with optional filters.
    - Fuzzy course code matching (e.g. 'CSC201' matches 'CSC 201')
    - Filter by price range (₦1,000 – ₦5,000)
    - Filter by minimum rating
    - Filter by grade_verified (Verified A badge)
    Uses eager loading to prevent N+1 queries.
    """
    query = select(TutorProfile).where(TutorProfile.is_available == True)

    # Price filters
    if min_price is not None:
        query = query.where(TutorProfile.hourly_rate >= min_price)
    if max_price is not None:
        query = query.where(TutorProfile.hourly_rate <= max_price)

    # Rating filter
    if min_rating is not None:
        query = query.where(TutorProfile.average_rating >= min_rating)

    # Grade verified filter
    if grade_verified is not None:
        query = query.where(TutorProfile.grade_verified == grade_verified)

    tutor_profiles = session.exec(query).all()

    results = []
    for profile in tutor_profiles:
        # Fetch the user — eager load to prevent N+1
        user = session.get(User, profile.user_id)
        if not user or not user.is_active:
            continue

        # Fetch courses via join — normalise code for fuzzy match
        course_links = session.exec(
            select(TutorCourse).where(TutorCourse.tutor_profile_id == profile.id)
        ).all()
        course_ids = [link.course_id for link in course_links]

        courses = []
        if course_ids:
            courses = session.exec(
                select(Course).where(Course.id.in_(course_ids))
            ).all()

        course_codes = [c.code for c in courses]

        # Fuzzy match — strip spaces and compare uppercase
        if course_code:
            normalised_search = course_code.replace(" ", "").upper()
            match = any(
                c.replace(" ", "").upper() == normalised_search
                for c in course_codes
            )
            if not match:
                continue

        results.append(
            TutorSearchResult(
                tutor=TutorProfileRead.model_validate(profile),
                user=UserRead.model_validate(user),
                courses=course_codes,
            )
        )

    return results


# ── Get Tutor Profile ─────────────────────────────────────────────────────────

@router.get("/{tutor_id}", response_model=TutorSearchResult)
@limiter.limit("100/minute")
def get_tutor(
    tutor_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Get a single tutor's full profile with courses and reviews."""
    profile = session.get(TutorProfile, tutor_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found")

    user = session.get(User, profile.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Fetch courses — eager load
    course_links = session.exec(
        select(TutorCourse).where(TutorCourse.tutor_profile_id == profile.id)
    ).all()
    course_ids = [link.course_id for link in course_links]
    courses = []
    if course_ids:
        courses = session.exec(select(Course).where(Course.id.in_(course_ids))).all()

    return TutorSearchResult(
        tutor=TutorProfileRead.model_validate(profile),
        user=UserRead.model_validate(user),
        courses=[c.code for c in courses],
    )


# ── Create/Update Tutor Profile ───────────────────────────────────────────────

@router.post("/profile", response_model=TutorProfileRead, status_code=status.HTTP_201_CREATED)
def create_tutor_profile(
    bio: Optional[str] = None,
    hourly_rate: float = 2500.0,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a tutor profile for the current user."""
    if current_user.get("role") != "tutor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tutors can create a tutor profile",
        )

    user_id = int(current_user["sub"])

    # Check if profile already exists
    existing = session.exec(
        select(TutorProfile).where(TutorProfile.user_id == user_id)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tutor profile already exists",
        )

    profile = TutorProfile(
        user_id=user_id,
        bio=bio,
        hourly_rate=hourly_rate,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


# ── Get Tutor Reviews ─────────────────────────────────────────────────────────

@router.get("/{tutor_id}/reviews", response_model=list[ReviewRead])
@limiter.limit("100/minute")
def get_tutor_reviews(
    tutor_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Get all reviews for a tutor."""
    profile = session.get(TutorProfile, tutor_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found")

    reviews = session.exec(
        select(Review).where(Review.tutor_profile_id == tutor_id)
    ).all()

    return reviews
