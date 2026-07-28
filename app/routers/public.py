"""
Public Tutor Profiles [E003-S03]
- Jinja2 templates for public-facing tutor profiles
- Open Graph (OG) meta tags for WhatsApp/Twitter link previews
- No authentication required — public pages
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from pathlib import Path

from app.database import get_session
from app.models import (
    TutorProfile, TutorCourse, Course, User,
)
from app.config import settings

router = APIRouter(prefix="/public", tags=["Public"])

# Set up Jinja2 templates
templates_path = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))


@router.get("/tutors/{tutor_id}", response_class=HTMLResponse)
async def public_tutor_profile(
    tutor_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """
    Public-facing tutor profile page.
    - Renders a beautiful HTML page with OG meta tags
    - No authentication needed
    - Shareable on WhatsApp, Twitter, Telegram
    """
    profile = session.get(TutorProfile, tutor_id)
    if not profile or not profile.is_available:
        raise HTTPException(status_code=404, detail="Tutor not found")

    user = session.get(User, profile.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch courses
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

    # Generate initials for avatar fallback
    initials = "".join(
        [w[0].upper() for w in user.full_name.split()[:2]]
    ) or "T"

    # Build OG image URL (use demo_video_url thumbnail or default)
    profile_image = profile.demo_video_url or f"https://ui-avatars.com/api/?name={initials}&size=200&background=667eea&color=fff"

    # Bio preview for OG description (truncated)
    bio = profile.bio or "Experienced tutor on Aced"
    bio_preview = bio[:150] + "..." if len(bio) > 150 else bio

    # Build page URL
    page_url = str(request.url)

    # Booking URL (frontend link)
    booking_url = f"{settings.FRONTEND_URL}/book/{tutor_id}"

    return templates.TemplateResponse(
        "tutor_profile.html",
        {
            "request": request,
            "tutor_name": user.full_name,
            "university": user.university or "University Student",
            "bio": bio,
            "bio_preview": bio_preview,
            "profile_image": profile_image,
            "initials": initials,
            "hourly_rate": f"{profile.hourly_rate:,.0f}",
            "average_rating": profile.average_rating,
            "total_reviews": profile.total_reviews,
            "grade_verified": profile.grade_verified,
            "courses": course_codes,
            "page_url": page_url,
            "booking_url": booking_url,
        },
    )
