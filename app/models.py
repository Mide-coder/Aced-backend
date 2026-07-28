from __future__ import annotations

from sqlmodel import SQLModel, Field
from enum import Enum
from typing import Optional
from datetime import datetime


class UserRole(str, Enum):
    student = "student"
    tutor = "tutor"


# University email domain → university name mapping
UNIVERSITY_DOMAIN_MAP: dict[str, str] = {
    "funaab.edu.ng": "Federal University of Agriculture, Abeokuta",
    "unilag.edu.ng": "University of Lagos",
    "ui.edu.ng": "University of Ibadan",
    "oau.edu.ng": "Obafemi Awolowo University",
    "abu.edu.ng": "Ahmadu Bello University",
    "uniben.edu.ng": "University of Benin",
    "unn.edu.ng": "University of Nigeria, Nsukka",
    "lasu.edu.ng": "Lagos State University",
    "yabatech.edu.ng": "Yaba College of Technology",
    "futa.edu.ng": "Federal University of Technology, Akure",
}


def detect_university_from_email(email: str) -> Optional[str]:
    """Auto-detect university name from email domain."""
    domain = email.split("@")[-1].lower()
    return UNIVERSITY_DOMAIN_MAP.get(domain)


class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    full_name: str
    role: UserRole = Field(default=UserRole.student)
    university: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)


class User(UserBase, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    created_at: datetime
    is_verified: bool


class UserUpdate(SQLModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None


# ── Verification Request [E001-S04] ───────────────────────────────────────────

class VerificationStatus(str, Enum):
    """Status of a manual identity verification request."""
    pending = "pending"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"


class VerificationRequest(SQLModel, table=True):
    __tablename__ = "verification_requests"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    # Storage path in Cloudflare R2
    matric_id_path: str  # e.g. "matric-ids/{user_id}/{uuid}.{ext}"

    # Auto-detected from email during registration
    detected_university: Optional[str] = None
    detected_email: str

    # Manual review fields
    status: VerificationStatus = Field(default=VerificationStatus.pending)
    reviewed_by: Optional[int] = Field(default=None, foreign_key="users.id")
    review_notes: Optional[str] = None
    rejection_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None


# ── Token Blacklist ───────────────────────────────────────────────────────────

class TokenBlacklist(SQLModel, table=True):
    __tablename__ = "token_blacklist"

    id: Optional[int] = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Course ────────────────────────────────────────────────────────────────────

class Course(SQLModel, table=True):
    __tablename__ = "courses"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)        # e.g. "CSC201"
    title: str                            # e.g. "Data Structures"
    department: Optional[str] = None
    university: Optional[str] = None
    difficulty: Optional[str] = Field(default=None)  # introductory, intermediate, advanced, expert
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── TutorProfile ──────────────────────────────────────────────────────────────

class TutorProfile(SQLModel, table=True):
    __tablename__ = "tutor_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)

    bio: Optional[str] = None
    hourly_rate: float = Field(default=2500.0)   # in Naira ₦1,000–₦5,000
    grade_verified: bool = Field(default=False)   # "Verified A" badge
    demo_video_url: Optional[str] = None          # Cloudflare R2 URL
    average_rating: float = Field(default=0.0)
    total_reviews: int = Field(default=0)
    is_available: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TutorProfileRead(SQLModel):
    id: int
    user_id: int
    bio: Optional[str]
    hourly_rate: float
    grade_verified: bool
    demo_video_url: Optional[str]
    average_rating: float
    total_reviews: int
    is_available: bool


# ── TutorCourse (many-to-many link) ──────────────────────────────────────────

class TutorCourse(SQLModel, table=True):
    __tablename__ = "tutor_courses"

    tutor_profile_id: Optional[int] = Field(
        default=None, foreign_key="tutor_profiles.id", primary_key=True
    )
    course_id: Optional[int] = Field(
        default=None, foreign_key="courses.id", primary_key=True
    )


# ── Review ────────────────────────────────────────────────────────────────────

class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: Optional[int] = Field(default=None, primary_key=True)
    tutor_profile_id: int = Field(foreign_key="tutor_profiles.id", index=True)
    student_id: int = Field(foreign_key="users.id")
    rating: float = Field(ge=1.0, le=5.0)
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewRead(SQLModel):
    id: int
    tutor_profile_id: int
    student_id: int
    rating: float
    comment: Optional[str]
    created_at: datetime


# ── Tutor Search Result ───────────────────────────────────────────────────────

class TutorSearchResult(SQLModel):
    tutor: TutorProfileRead
    user: UserRead
    courses: list[str] = []   # list of course codes


# ── Booking State Machine [E004-S02] ──────────────────────────────────────────

class BookingStatus(str, Enum):
    pending = "pending"                 # Initial state
    paid_escrow = "paid_escrow"        # Payment received, held in escrow
    completed = "completed"             # Session completed, awaiting fund release
    funds_released = "funds_released"   # Tutor paid
    cancelled = "cancelled"             # Student cancelled
    refunded = "refunded"               # Refund processed


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="users.id", index=True)
    tutor_profile_id: int = Field(foreign_key="tutor_profiles.id", index=True)

    status: BookingStatus = Field(default=BookingStatus.pending)

    session_datetime: datetime
    duration_hours: int = Field(default=1, ge=1, le=4)
    total_price: float
    deposit_amount: float = Field(default=0.0)  # 20% non-refundable if cancelled <24h

    # Paystack integration
    paystack_reference: Optional[str] = Field(default=None, unique=True, index=True)
    payment_completed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BookingRead(SQLModel):
    id: int
    student_id: int
    tutor_profile_id: int
    status: BookingStatus
    session_datetime: datetime
    duration_hours: int
    total_price: float
    deposit_amount: float
    paystack_reference: Optional[str]
    created_at: datetime


class BookingCreate(SQLModel):
    tutor_profile_id: int
    course_id: Optional[int] = Field(default=None, description="Optional — used for per-course tiered pricing")
    session_datetime: datetime
    duration_hours: int = Field(default=1, ge=1, le=4)


# ── Availability Slots [E003-S02] ─────────────────────────────────────────────

class AvailabilitySlot(SQLModel, table=True):
    __tablename__ = "availability_slots"

    id: Optional[int] = Field(default=None, primary_key=True)
    tutor_profile_id: int = Field(foreign_key="tutor_profiles.id", index=True)

    day_of_week: int = Field(ge=0, le=6)  # 0=Monday, 6=Sunday
    start_time: str  # e.g. "14:00" (24h format)
    end_time: str    # e.g. "16:00"

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AvailabilitySlotRead(SQLModel):
    id: int
    tutor_profile_id: int
    day_of_week: int
    start_time: str
    end_time: str
    is_active: bool


class AvailabilitySlotCreate(SQLModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str


# ── Financial Payout Ledger (Sprint 3) ────────────────────────────────────────

class TransactionType(str, Enum):
    """Types of financial transactions in the payout ledger."""
    session_payment = "session_payment"         # Student pays for session
    deposit_forfeited = "deposit_forfeited"     # 20% deposit forfeited on late cancel
    refund = "refund"                           # Full/partial refund to student
    tutor_payout = "tutor_payout"              # Manual bank transfer to tutor
    platform_fee = "platform_fee"              # Platform commission (future)


class PayoutLedger(SQLModel, table=True):
    __tablename__ = "payout_ledger"

    id: Optional[int] = Field(default=None, primary_key=True)
    booking_id: int = Field(foreign_key="bookings.id", index=True)

    # Financial details
    transaction_type: TransactionType
    amount: float          # Positive = inflow to platform, Negative = outflow
    description: str

    # Settlement tracking (manual bank transfers)
    tutor_id: Optional[int] = Field(default=None, foreign_key="users.id")
    tutor_paid: bool = Field(default=False)
    tutor_paid_at: Optional[datetime] = None
    payment_method: Optional[str] = None  # e.g. "manual_bank_transfer"

    created_at: datetime = Field(default_factory=datetime.utcnow)


class PayoutLedgerRead(SQLModel):
    id: int
    booking_id: int
    transaction_type: TransactionType
    amount: float
    description: str
    tutor_paid: bool
    created_at: datetime
