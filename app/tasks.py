"""
Background Tasks [E004-S04]
- Session reminders via WhatsApp Sandbox
- Triggered by Celery Beat at 24h and 1h before session start

Note: During the pilot, WhatsApp notifications use the Meta WhatsApp Sandbox
(limited to verified test numbers). For production, a WhatsApp Business API
subscription is needed.
"""

import os
import httpx
import logging
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select

from app.celery_app import celery_app
from app.database import engine
from app.models import Booking, BookingStatus, User

logger = logging.getLogger("aced.tasks")

# WhatsApp Sandbox configuration — read directly from env
WHATSAPP_API_URL = "https://graph.facebook.com/v18.0/{phone_number_id}/messages"
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")


def _send_whatsapp_message(to_phone: str, message: str) -> bool:
    """
    Send a WhatsApp message via the Meta WhatsApp Cloud API Sandbox.

    Args:
        to_phone: Recipient phone number in international format (e.g. 2348123456789)
        message: The message text to send

    Returns:
        True if sent successfully, False otherwise
    """
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("WhatsApp not configured — skipping message to %s", to_phone)
        return False

    url = WHATSAPP_API_URL.format(phone_number_id=WHATSAPP_PHONE_NUMBER_ID)
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": "session_reminder",
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": message}],
                }
            ],
        },
    }

    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                logger.info("WhatsApp message sent to %s", to_phone)
                return True
            else:
                logger.error(
                    "WhatsApp API error for %s: %s",
                    to_phone,
                    response.text,
                )
                return False
    except Exception as e:
        logger.error("Failed to send WhatsApp message to %s: %s", to_phone, str(e))
        return False


@celery_app.task
def send_session_reminder_24h():
    """
    Scheduled task — runs hourly.
    Finds bookings starting in ~24 hours and sends a reminder.
    """
    logger.info("Checking for 24h session reminders...")
    now = datetime.now(timezone.utc)
    target_start = now + timedelta(hours=24)

    with Session(engine) as session:
        bookings = session.exec(
            select(Booking)
            .where(Booking.status == BookingStatus.paid_escrow)
            .where(
                Booking.session_datetime >= target_start - timedelta(minutes=30),
            )
            .where(
                Booking.session_datetime <= target_start + timedelta(minutes=30),
            )
        ).all()

        for booking in bookings:
            student = session.get(User, booking.student_id)
            if student and student.is_active:
                message = (
                    f"🎓 Reminder: Your tutoring session is in 24 hours!\n"
                    f"📅 {booking.session_datetime.strftime('%A, %B %d at %I:%M %p')}\n"
                    f"⏱ Duration: {booking.duration_hours}h\n"
                    f"💰 Total: ₦{booking.total_price:,.2f}"
                )
                _send_whatsapp_message(student.phone or "", message)

    logger.info("24h reminder check complete — %d reminders sent", len(bookings))


@celery_app.task
def send_session_reminder_1h():
    """
    Scheduled task — runs every 30 minutes.
    Finds bookings starting in ~1 hour and sends a reminder.
    """
    logger.info("Checking for 1h session reminders...")
    now = datetime.now(timezone.utc)
    target_start = now + timedelta(hours=1)

    with Session(engine) as session:
        bookings = session.exec(
            select(Booking)
            .where(Booking.status == BookingStatus.paid_escrow)
            .where(
                Booking.session_datetime >= target_start - timedelta(minutes=10),
            )
            .where(
                Booking.session_datetime <= target_start + timedelta(minutes=10),
            )
        ).all()

        for booking in bookings:
            student = session.get(User, booking.student_id)
            if student and student.is_active:
                message = (
                    f"⏰ Hurry! Your session starts in 1 hour!\n"
                    f"📅 {booking.session_datetime.strftime('%A, %B %d at %I:%M %p')}\n"
                    f"⏱ Duration: {booking.duration_hours}h\n"
                    f"🔗 Join link: [Link TBD]"
                )
                _send_whatsapp_message(student.phone or "", message)

    logger.info("1h reminder check complete — %d reminders sent", len(bookings))
