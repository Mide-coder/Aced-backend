import hmac
import hashlib
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlmodel import Session, select

from app.database import get_session
from app.models import Booking, BookingStatus, User
from app.auth import get_current_user
from app.config import settings
from app.rate_limit import limiter

router = APIRouter(prefix="/payments", tags=["Payments"])


# ── Paystack Webhook [E005-S01] ───────────────────────────────────────────────

@router.post("/paystack-webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(None),
    session: Session = Depends(get_session),
):
    """
    Paystack webhook handler with idempotency.
    - Validates signature
    - Updates booking to PAID_ESCROW on successful payment
    - Idempotent: handles duplicate webhook calls safely
    """
    body = await request.body()

    # Verify signature
    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET.encode("utf-8"),
        body,
        hashlib.sha512,
    ).hexdigest()

    if x_paystack_signature != computed_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # Parse event
    event = await request.json()
    event_type = event.get("event")

    if event_type == "charge.success":
        data = event.get("data", {})
        reference = data.get("reference")
        amount = data.get("amount")  # in kobo (₦1 = 100 kobo)

        if not reference:
            return {"message": "No reference in webhook"}

        # Find booking by reference — idempotency key
        booking = session.exec(
            select(Booking).where(Booking.paystack_reference == reference)
        ).first()

        if not booking:
            # Idempotency: reference doesn't match any booking, ignore
            return {"message": "Booking not found, ignored"}

        # Idempotency: already processed
        if booking.status == BookingStatus.paid_escrow:
            return {"message": "Payment already processed"}

        # Validate amount matches (convert kobo to naira)
        expected_amount_kobo = int(booking.total_price * 100)
        if amount != expected_amount_kobo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Amount mismatch: expected {expected_amount_kobo}, got {amount}",
            )

        # Update booking status: PENDING → PAID_ESCROW
        from app.routers.bookings import validate_state_transition

        if not validate_state_transition(booking.status, BookingStatus.paid_escrow):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid state transition from {booking.status}",
            )

        booking.status = BookingStatus.paid_escrow
        session.add(booking)
        session.commit()

        return {"message": "Payment processed successfully"}

    return {"message": "Event type not handled"}


# ── Initialize Payment ────────────────────────────────────────────────────────

@router.post("/initialize")
@limiter.limit("10/minute")
async def initialize_payment(
    booking_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Initialize a Paystack payment for a booking.
    Returns payment URL for the student to complete.
    Uses the authenticated student's email and the configured FRONTEND_URL.
    """
    booking = session.get(Booking, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    user_id = int(current_user["sub"])
    if booking.student_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only pay for your own bookings",
        )

    if booking.status != BookingStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot initialize payment for booking in state {booking.status}",
        )

    student = session.get(User, user_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    # Generate unique reference (idempotency key)
    import uuid
    reference = f"BK-{booking.id}-{uuid.uuid4().hex[:8]}"

    # Call Paystack API
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": student.email,
        "amount": int(booking.total_price * 100),  # Convert to kobo
        "reference": reference,
        "callback_url": f"{settings.FRONTEND_URL}/payment-callback.html",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Paystack API error",
        )

    data = response.json().get("data", {})
    authorization_url = data.get("authorization_url")

    # Save reference to booking
    booking.paystack_reference = reference
    session.add(booking)
    session.commit()

    return {
        "authorization_url": authorization_url,
        "reference": reference,
    }
