from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select
from datetime import datetime, timezone, timedelta
import hmac
import hashlib

from app.database import get_session
from app.models import (
    Booking, BookingRead, BookingCreate, BookingStatus,
    TutorProfile, AvailabilitySlot, AvailabilitySlotRead, AvailabilitySlotCreate,
)
from app.auth import get_current_user
from app.config import settings
from app.rate_limit import limiter

router = APIRouter(prefix="/bookings", tags=["Bookings"])


# ── State Machine Validation [E004-S02] ───────────────────────────────────────

VALID_STATE_TRANSITIONS = {
    BookingStatus.pending: [BookingStatus.paid_escrow, BookingStatus.cancelled],
    BookingStatus.paid_escrow: [BookingStatus.completed, BookingStatus.cancelled],
    BookingStatus.completed: [BookingStatus.funds_released],
    BookingStatus.funds_released: [],  # Terminal state
    BookingStatus.cancelled: [BookingStatus.refunded],
    BookingStatus.refunded: [],  # Terminal state
}


def validate_state_transition(current: BookingStatus, target: BookingStatus) -> bool:
    """Enforce rigid state machine — must follow allowed transitions only."""
    return target in VALID_STATE_TRANSITIONS.get(current, [])


# ── Create Booking ────────────────────────────────────────────────────────────

@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_in: BookingCreate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Create a new booking in PENDING state.
    - Student books a session with a tutor
    - Total price calculated from tutor's hourly rate
    - Initial state: PENDING (awaiting payment)
    """
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can create bookings",
        )

    student_id = int(current_user["sub"])

    # Validate tutor exists
    tutor = session.get(TutorProfile, booking_in.tutor_profile_id)
    if not tutor or not tutor.is_available:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tutor not found or unavailable",
        )

    # Calculate total price
    total_price = tutor.hourly_rate * booking_in.duration_hours
    deposit_amount = total_price * 0.20  # 20% deposit for cancellation protection

    booking = Booking(
        student_id=student_id,
        tutor_profile_id=booking_in.tutor_profile_id,
        session_datetime=booking_in.session_datetime,
        duration_hours=booking_in.duration_hours,
        total_price=total_price,
        deposit_amount=deposit_amount,
        status=BookingStatus.pending,
    )

    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


# ── Update Booking Status (State Machine Enforced) ───────────────────────────

@router.patch("/{booking_id}/status")
def update_booking_status(
    booking_id: int,
    target_status: BookingStatus,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Update booking status with rigid state machine enforcement.
    Returns 400 Bad Request if transition is invalid.
    """
    booking = session.get(Booking, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # Validate state transition
    if not validate_state_transition(booking.status, target_status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state transition: {booking.status} → {target_status}",
        )

    booking.status = target_status
    booking.updated_at = datetime.utcnow()

    # Track payment completion time
    if target_status == BookingStatus.paid_escrow:
        booking.payment_completed_at = datetime.utcnow()

    session.add(booking)
    session.commit()
    session.refresh(booking)

    return {"message": f"Booking status updated to {target_status}", "booking": booking}


# ── Get My Bookings ───────────────────────────────────────────────────────────

@router.get("/my-bookings", response_model=list[BookingRead])
@limiter.limit("100/minute")
def get_my_bookings(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get all bookings for the current user (student or tutor)."""
    user_id = int(current_user["sub"])
    role = current_user.get("role")

    if role == "student":
        bookings = session.exec(
            select(Booking).where(Booking.student_id == user_id)
        ).all()
    elif role == "tutor":
        # Get tutor profile first
        tutor_profile = session.exec(
            select(TutorProfile).where(TutorProfile.user_id == user_id)
        ).first()
        if not tutor_profile:
            return []
        bookings = session.exec(
            select(Booking).where(Booking.tutor_profile_id == tutor_profile.id)
        ).all()
    else:
        return []

    return bookings


# ── Cancel Booking with Commitment Logic [E004-S03] ───────────────────────────

@router.post("/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Cancel a booking.
    - If cancelled <24h before session: 20% deposit is non-refundable
    - Otherwise: full refund
    """
    booking = session.get(Booking, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    student_id = int(current_user["sub"])
    if booking.student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own bookings",
        )

    # State machine: can only cancel from pending or paid_escrow
    if not validate_state_transition(booking.status, BookingStatus.cancelled):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel booking in state {booking.status}",
        )

    # Check if within 24 hours of session
    now = datetime.now(timezone.utc)
    time_until_session = booking.session_datetime - now
    within_24h = time_until_session < timedelta(hours=24)

    refund_amount = booking.total_price
    if within_24h:
        # 20% deposit is non-refundable
        refund_amount = booking.total_price - booking.deposit_amount

    booking.status = BookingStatus.cancelled
    booking.updated_at = datetime.utcnow()
    session.add(booking)
    session.commit()

    return {
        "message": "Booking cancelled",
        "refund_amount": refund_amount,
        "deposit_forfeited": within_24h,
    }


# ── Availability Management [E003-S02] ────────────────────────────────────────

@router.post("/availability", response_model=AvailabilitySlotRead, status_code=status.HTTP_201_CREATED)
def create_availability_slot(
    slot_in: AvailabilitySlotCreate,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a recurring availability slot (1-hour blocks)."""
    if current_user.get("role") != "tutor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tutors can create availability slots",
        )

    user_id = int(current_user["sub"])
    tutor_profile = session.exec(
        select(TutorProfile).where(TutorProfile.user_id == user_id)
    ).first()

    if not tutor_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tutor profile not found",
        )

    slot = AvailabilitySlot(
        tutor_profile_id=tutor_profile.id,
        day_of_week=slot_in.day_of_week,
        start_time=slot_in.start_time,
        end_time=slot_in.end_time,
    )

    session.add(slot)
    session.commit()
    session.refresh(slot)
    return slot


@router.get("/availability/{tutor_id}", response_model=list[AvailabilitySlotRead])
@limiter.limit("100/minute")
def get_tutor_availability(
    tutor_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Get all availability slots for a tutor."""
    slots = session.exec(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.tutor_profile_id == tutor_id)
        .where(AvailabilitySlot.is_active == True)
    ).all()
    return slots
