"""
Seed demo data for Aced — makes the full flow demoable end-to-end.

Creates (idempotent — safe to re-run):
  - Demo student + 5 demo tutors with profiles, courses, availability, reviews
  - Bookings across the full escrow state machine (pending → paid_escrow → completed → funds_released)
  - Payout ledger entries for completed sessions
  - Resets the admin account (user id=1) password so admin.html can be logged into

Demo credentials (all passwords below):
  Admin  : student@funaab.edu.ng / Admin@1234
  Student: demo.student@funaab.edu.ng / Demo@1234
  Tutors : tomi.fashola@funaab.edu.ng / Demo@1234  (and 4 others, same password)
"""

from datetime import datetime, timedelta
from sqlmodel import Session, select

from app.database import engine
from app.models import (
    User, UserRole, TutorProfile, Course, TutorCourse, Review,
    Booking, BookingStatus, AvailabilitySlot, PayoutLedger, TransactionType,
)
from app.auth import hash_password

ADMIN_PASSWORD = "Admin@1234"
DEMO_PASSWORD = "Demo@1234"

# ── Demo tutor definitions ────────────────────────────────────────────────────

TUTORS = [
    {
        "email": "tomi.fashola@funaab.edu.ng",
        "full_name": "Tomi Fashola",
        "bio": "4th-year Statistics major. I make hypothesis testing, regression and probability click — patient, step-by-step explanations with real past questions.",
        "hourly_rate": 3500.0,
        "grade_verified": True,
        "courses": ["MAT101", "MAT102", "MAT201", "MAT303"],
        "availability": [
            {"day_of_week": 0, "start_time": "09:00", "end_time": "12:00"},
            {"day_of_week": 0, "start_time": "14:00", "end_time": "17:00"},
            {"day_of_week": 2, "start_time": "10:00", "end_time": "13:00"},
            {"day_of_week": 4, "start_time": "09:00", "end_time": "13:00"},
        ],
    },
    {
        "email": "michael.adeyemi@funaab.edu.ng",
        "full_name": "Michael Adeyemi",
        "bio": "Computer Science undergrad with an 'A' in CSC301. I teach Data Structures, Algorithms and Python from first principles.",
        "hourly_rate": 3000.0,
        "grade_verified": True,
        "courses": ["CSC101", "CSC201", "CSC301", "MAT201"],
        "availability": [
            {"day_of_week": 1, "start_time": "14:00", "end_time": "18:00"},
            {"day_of_week": 3, "start_time": "09:00", "end_time": "12:00"},
            {"day_of_week": 5, "start_time": "10:00", "end_time": "14:00"},
        ],
    },
    {
        "email": "blessing.ogunlade@funaab.edu.ng",
        "full_name": "Blessing Ogunlade",
        "bio": "Biochemistry student. Organic Chemistry, General Chemistry and Biology made simple with mnemonics and exam-focused drills.",
        "hourly_rate": 3500.0,
        "grade_verified": True,
        "courses": ["CHM101", "CHM201", "BIO101", "BIO201"],
        "availability": [
            {"day_of_week": 0, "start_time": "14:00", "end_time": "17:00"},
            {"day_of_week": 2, "start_time": "09:00", "end_time": "12:00"},
            {"day_of_week": 4, "start_time": "14:00", "end_time": "16:00"},
        ],
    },
    {
        "email": "david.ogunlade@funaab.edu.ng",
        "full_name": "David Ogunlade",
        "bio": "Engineering student who lives for Physics. From Newtonian mechanics to electromagnetism — real intuition, not just formulas.",
        "hourly_rate": 4000.0,
        "grade_verified": True,
        "courses": ["PHY101", "PHY102", "PHY201", "ENG101"],
        "availability": [
            {"day_of_week": 1, "start_time": "09:00", "end_time": "12:00"},
            {"day_of_week": 3, "start_time": "14:00", "end_time": "17:00"},
            {"day_of_week": 5, "start_time": "09:00", "end_time": "13:00"},
        ],
    },
    {
        "email": "kemi.eze@funaab.edu.ng",
        "full_name": "Kemi Eze",
        "bio": "Agricultural Economics student. I help with microeconomics, farm management and agricultural marketing — practical and relatable.",
        "hourly_rate": 2500.0,
        "grade_verified": False,
        "courses": ["AEC101", "AEC201", "AEC301", "GST101"],
        "availability": [
            {"day_of_week": 2, "start_time": "14:00", "end_time": "17:00"},
            {"day_of_week": 4, "start_time": "10:00", "end_time": "13:00"},
            {"day_of_week": 6, "start_time": "12:00", "end_time": "16:00"},
        ],
    },
]


def get_course_by_code(session: Session, code: str) -> Course:
    return session.exec(select(Course).where(Course.code == code)).first()


def seed_demo():
    with Session(engine) as session:
        created_tutors = []

        # ── Demo student ────────────────────────────────────────────────────
        student = session.exec(
            select(User).where(User.email == "demo.student@funaab.edu.ng")
        ).first()
        if not student:
            student = User(
                email="demo.student@funaab.edu.ng",
                full_name="Demo Student",
                role=UserRole.student,
                university="Federal University of Agriculture, Abeokuta",
                hashed_password=hash_password(DEMO_PASSWORD),
                is_verified=True,
            )
            session.add(student)
            session.commit()
            session.refresh(student)
            print(f"[OK] Created demo student (id={student.id})")
        else:
            print(f"[OK] Demo student already exists (id={student.id})")

        # ── Reset admin password (user id=1) ────────────────────────────────
        admin = session.get(User, 1)
        if admin:
            admin.hashed_password = hash_password(ADMIN_PASSWORD)
            session.add(admin)

        # ── Tutors ──────────────────────────────────────────────────────────
        for t in TUTORS:
            user = session.exec(select(User).where(User.email == t["email"])).first()
            if not user:
                user = User(
                    email=t["email"],
                    full_name=t["full_name"],
                    role=UserRole.tutor,
                    university="Federal University of Agriculture, Abeokuta",
                    hashed_password=hash_password(DEMO_PASSWORD),
                    is_verified=True,
                )
                session.add(user)
                session.commit()
                session.refresh(user)

            # Tutor profile
            profile = session.exec(
                select(TutorProfile).where(TutorProfile.user_id == user.id)
            ).first()
            if not profile:
                profile = TutorProfile(
                    user_id=user.id,
                    bio=t["bio"],
                    hourly_rate=t["hourly_rate"],
                    grade_verified=t["grade_verified"],
                    is_available=True,
                )
                session.add(profile)
                session.commit()
                session.refresh(profile)
                print(f"[OK] Created tutor profile for {user.full_name} (id={profile.id})")

            profile.hourly_rate = t["hourly_rate"]
            profile.grade_verified = t["grade_verified"]
            profile.is_available = True
            profile.bio = t["bio"]
            session.add(profile)

            # Course links
            for code in t["courses"]:
                course = get_course_by_code(session, code)
                if not course:
                    continue
                exists = session.exec(
                    select(TutorCourse).where(
                        TutorCourse.tutor_profile_id == profile.id,
                        TutorCourse.course_id == course.id,
                    )
                ).first()
                if not exists:
                    session.add(TutorCourse(tutor_profile_id=profile.id, course_id=course.id))

            # Availability slots
            for slot in t["availability"]:
                exists = session.exec(
                    select(AvailabilitySlot).where(
                        AvailabilitySlot.tutor_profile_id == profile.id,
                        AvailabilitySlot.day_of_week == slot["day_of_week"],
                        AvailabilitySlot.start_time == slot["start_time"],
                    )
                ).first()
                if not exists:
                    session.add(AvailabilitySlot(
                        tutor_profile_id=profile.id,
                        day_of_week=slot["day_of_week"],
                        start_time=slot["start_time"],
                        end_time=slot["end_time"],
                        is_active=True,
                    ))

            created_tutors.append((user, profile))

        session.commit()

        # ── Reviews (from the demo student) ──────────────────────────────────
        now = datetime.utcnow()
        review_data = [
            (created_tutors[0][1], 5.0, "Tomi broke down hypothesis testing so clearly — finally understand p-values! Booked again immediately."),
            (created_tutors[1][1], 5.0, "Michael made linked lists and recursion actually fun. My best tutoring session so far."),
            (created_tutors[2][1], 4.5, "Blessing is very patient and great with mnemonics for Organic Chemistry."),
            (created_tutors[3][1], 5.0, "David explains Physics with real intuition — I stopped memorising formulas after session one."),
            (created_tutors[4][1], 4.0, "Kemi is good with microeconomics concepts, very practical examples."),
        ]
        for profile, rating, comment in review_data:
            exists = session.exec(
                select(Review).where(
                    Review.tutor_profile_id == profile.id,
                    Review.student_id == student.id,
                )
            ).first()
            if not exists:
                session.add(Review(
                    tutor_profile_id=profile.id,
                    student_id=student.id,
                    rating=rating,
                    comment=comment,
                    created_at=now - timedelta(days=2),
                ))

        session.commit()

        # Recompute tutor rating aggregates
        for _, profile in created_tutors:
            reviews = session.exec(
                select(Review).where(Review.tutor_profile_id == profile.id)
            ).all()
            if reviews:
                profile.average_rating = round(
                    sum(r.rating for r in reviews) / len(reviews), 1
                )
                profile.total_reviews = len(reviews)
            session.add(profile)
        session.commit()

        # ── Bookings across the escrow state machine ─────────────────────────
        (tomi, michael, blessing, david, kemi) = [p for _, p in created_tutors]

        def make_booking(tutor_profile, status, days_from_now, hour=14, hours=1, ref=None):
            existing = None
            if ref:
                existing = session.exec(
                    select(Booking).where(Booking.paystack_reference == ref)
                ).first()
            if existing:
                return existing
            session_dt = (now + timedelta(days=days_from_now)).replace(hour=hour, minute=0, second=0, microsecond=0)
            total = tutor_profile.hourly_rate * hours
            booking = Booking(
                student_id=student.id,
                tutor_profile_id=tutor_profile.id,
                status=status,
                session_datetime=session_dt,
                duration_hours=hours,
                total_price=total,
                deposit_amount=round(total * 0.20, 2),
                paystack_reference=ref,
                payment_completed_at=now - timedelta(days=3) if status in (
                    BookingStatus.paid_escrow,
                    BookingStatus.completed,
                    BookingStatus.funds_released,
                ) else None,
            )
            session.add(booking)
            session.commit()
            session.refresh(booking)
            return booking

        b1 = make_booking(tomi, BookingStatus.paid_escrow, 3, hour=14, ref="BK-DEMO-0001")
        b2 = make_booking(michael, BookingStatus.pending, 5, hour=10, ref=None)
        b3 = make_booking(blessing, BookingStatus.completed, -6, hour=16, ref="BK-DEMO-0002")
        b4 = make_booking(david, BookingStatus.funds_released, -12, hour=11, hours=2, ref="BK-DEMO-0003")
        b5 = make_booking(kemi, BookingStatus.cancelled, -20, hour=15, ref=None)
        b6 = make_booking(tomi, BookingStatus.completed, -28, hour=9, ref="BK-DEMO-0004")

        # ── Payout ledger ────────────────────────────────────────────────────
        for booking, tutor_user in [(b3, created_tutors[2][0]), (b4, created_tutors[3][0]), (b6, created_tutors[0][0])]:
            exists = session.exec(
                select(PayoutLedger).where(
                    PayoutLedger.booking_id == booking.id,
                    PayoutLedger.transaction_type == TransactionType.session_payment,
                )
            ).first()
            if not exists:
                session.add(PayoutLedger(
                    booking_id=booking.id,
                    transaction_type=TransactionType.session_payment,
                    amount=booking.total_price,
                    description=f"Session payment for booking #{booking.id} — {booking.duration_hours}h",
                ))
            # Mark completed→payout for funds_released bookings
            if booking.status == BookingStatus.funds_released:
                payout = session.exec(
                    select(PayoutLedger).where(
                        PayoutLedger.booking_id == booking.id,
                        PayoutLedger.transaction_type == TransactionType.tutor_payout,
                    )
                ).first()
                if not payout:
                    session.add(PayoutLedger(
                        booking_id=booking.id,
                        transaction_type=TransactionType.tutor_payout,
                        amount=booking.total_price,
                        description=f"Manual bank transfer for booking #{booking.id}",
                        tutor_id=tutor_user.id,
                        tutor_paid=True,
                        tutor_paid_at=now - timedelta(days=1),
                        payment_method="manual_bank_transfer",
                    ))
        session.commit()

        # ── Mark any stale tutor profiles (no courses) unavailable ───────────
        stale = session.exec(select(TutorProfile)).all()
        for p in stale:
            links = session.exec(
                select(TutorCourse).where(TutorCourse.tutor_profile_id == p.id)
            ).all()
            if not links:
                p.is_available = False
                session.add(p)
        session.commit()

        # ── Verify counts ────────────────────────────────────────────────────
        tutors_count = len(session.exec(select(TutorProfile)).all())
        bookings_count = len(session.exec(select(Booking)).all())
        reviews_count = len(session.exec(select(Review)).all())
        print(f"[OK] Seeding complete — tutors: {tutors_count}, bookings: {bookings_count}, reviews: {reviews_count}")


if __name__ == "__main__":
    print("[...] Seeding demo data...")
    seed_demo()
    print("=" * 60)
    print("DEMO CREDENTIALS")
    print("=" * 60)
    print("Admin   : student@funaab.edu.ng  / Admin@1234   (admin.html)")
    print("Student : demo.student@funaab.edu.ng / Demo@1234 (dashboard.html)")
    print("Tutor   : tomi.fashola@funaab.edu.ng / Demo@1234  (tutor-dashboard.html)")
    print("=" * 60)
