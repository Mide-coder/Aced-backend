"""
Admin Router — Sprint 2 & 3
- Grade/Transcript Verification [E002-S02]: Toggle grade_verified on tutor profiles
- Identity/Matric Verification [E001-S04]: Review and approve/reject verification requests
- Financial Payout Ledger: View completed sessions for manual bank transfer tracking
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from datetime import datetime
from typing import Optional

from app.database import get_session
from app.models import (
    User, UserRole,
    TutorProfile, TutorProfileRead,
    Booking, BookingStatus,
    VerificationRequest, VerificationStatus,
    PayoutLedger, PayoutLedgerRead, TransactionType,
)
from app.auth import get_current_user
from app.rate_limit import limiter

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Admin Auth Helper ─────────────────────────────────────────────────────────

def _require_admin(current_user: dict) -> int:
    """
    Require that the current user has an admin-level role.
    During pilot, admins are identified by is_verified + tutor role.
    For true admin access, we check if user_id == 1 (first seeded admin)
    or check a designated admin email list.
    """
    user_id = int(current_user["sub"])
    # During pilot: User ID 1 is treated as admin
    if user_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user_id


# ── Grade Verification [E002-S02] ─────────────────────────────────────────────

class GradeVerificationUpdate(BaseModel):
    """Request body for toggling grade_verified on a tutor profile."""
    grade_verified: bool
    notes: Optional[str] = None


@router.patch("/tutors/{tutor_id}/grade-verify", response_model=TutorProfileRead)
@limiter.limit("30/minute")
def toggle_grade_verification(
    tutor_id: int,
    request: Request,
    body: GradeVerificationUpdate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    [E002-S02] Toggle the 'Verified A' badge on a tutor profile.

    **Manual OCR Process (Mide):**
    1. Review uploaded transcript screenshot (via /media/upload/matric-id)
    2. Verify the grade matches the course in our database
    3. Call this endpoint to award the "Verified A" badge

    This is the "Human OCR" step — no automated OCR needed during pilot.
    """
    admin_id = _require_admin(current_user)

    profile = session.get(TutorProfile, tutor_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tutor profile not found",
        )

    profile.grade_verified = body.grade_verified
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)

    return profile


# ── Verification Requests [E001-S04] ──────────────────────────────────────────

@router.get("/verification-requests")
@limiter.limit("30/minute")
def list_verification_requests(
    request: Request,
    status_filter: Optional[VerificationStatus] = None,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    List all identity verification requests.
    Optionally filter by status: pending, under_review, approved, rejected.
    """
    _require_admin(current_user)

    query = select(VerificationRequest)
    if status_filter:
        query = query.where(VerificationRequest.status == status_filter)

    query = query.order_by(VerificationRequest.created_at.desc())
    requests = session.exec(query).all()
    return requests


class VerificationReview(BaseModel):
    """Request body for reviewing a verification request."""
    status: VerificationStatus  # approved or rejected
    review_notes: Optional[str] = None
    rejection_reason: Optional[str] = None


@router.patch("/verification-requests/{request_id}")
@limiter.limit("30/minute")
def review_verification_request(
    request_id: int,
    request: Request,
    body: VerificationReview,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Review and approve/reject a matric ID verification request.

    **Manual Verification Criteria:**
    1. Matric ID must clearly display student's full name matching account
    2. Must show university matching auto-detected university from email
    3. Registration number follows valid Nigerian university format
    4. Photo must match user (if applicable)
    5. Document must not be expired or tampered with
    """
    admin_id = _require_admin(current_user)

    ver_request = session.get(VerificationRequest, request_id)
    if not ver_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification request not found",
        )

    # Only review pending or under_review requests
    if ver_request.status not in (VerificationStatus.pending, VerificationStatus.under_review):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot review request in status '{ver_request.status}'",
        )

    ver_request.status = body.status
    ver_request.reviewed_by = admin_id
    ver_request.review_notes = body.review_notes
    ver_request.rejection_reason = body.rejection_reason
    ver_request.reviewed_at = datetime.utcnow()

    # If approved, mark the user as verified
    if body.status == VerificationStatus.approved:
        user = session.get(User, ver_request.user_id)
        if user:
            user.is_verified = True
            session.add(user)

    session.add(ver_request)
    session.commit()
    session.refresh(ver_request)

    return ver_request


# ── Payout Ledger ─────────────────────────────────────────────────────────────

@router.get("/payout-ledger", response_model=list[PayoutLedgerRead])
@limiter.limit("30/minute")
def get_payout_ledger(
    request: Request,
    tutor_paid: Optional[bool] = None,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    View the financial payout ledger.
    Tracks COMPLETED sessions for weekly manual bank transfers to tutors.
    """
    _require_admin(current_user)

    query = select(PayoutLedger)
    if tutor_paid is not None:
        query = query.where(PayoutLedger.tutor_paid == tutor_paid)

    query = query.order_by(PayoutLedger.created_at.desc())
    entries = session.exec(query).all()
    return entries


@router.post("/payout-ledger/{booking_id}/record-payout")
@limiter.limit("20/minute")
def record_tutor_payout(
    booking_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Record a manual bank transfer payout to a tutor for a COMPLETED booking.
    This updates the payout ledger to mark the tutor as paid.
    """
    admin_id = _require_admin(current_user)

    booking = session.get(Booking, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    if booking.status != BookingStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking must be COMPLETED before payout. Current status: {booking.status}",
        )

    # Create payout ledger entry
    tutor_profile = session.get(TutorProfile, booking.tutor_profile_id)
    if not tutor_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor profile not found")

    payout_entry = PayoutLedger(
        booking_id=booking_id,
        transaction_type=TransactionType.tutor_payout,
        amount=booking.total_price,
        description=f"Manual bank transfer for booking #{booking_id} — {booking.duration_hours}h session",
        tutor_id=tutor_profile.user_id,
        tutor_paid=True,
        tutor_paid_at=datetime.utcnow(),
        payment_method="manual_bank_transfer",
    )

    # Also update booking status to funds_released
    booking.status = BookingStatus.funds_released
    booking.updated_at = datetime.utcnow()

    session.add(payout_entry)
    session.add(booking)
    session.commit()
    session.refresh(payout_entry)

    return {
        "message": "Payout recorded successfully",
        "payout": payout_entry,
    }
