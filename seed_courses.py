#!/usr/bin/env python3
"""
Database Seeding Script [E003-S01]
Compiles 50+ real course codes for FUNAAB (Federal University of Agriculture, Abeokuta)
and seeds the Course table using SQLModel.

Usage:
    uv run python seed_courses.py          # Run with uv
    python seed_courses.py                  # Run directly

This script is idempotent — running it multiple times won't create duplicates.
"""

from sqlmodel import Session, select
from app.database import engine, create_db_and_tables
from app.models import Course

# ── FUNAAB Course Data ────────────────────────────────────────────────────────
# Federal University of Agriculture, Abeokuta (FUNAAB) — Pilot Campus
# Real course codes collected from FUNAAB academic curriculum

FUNAAB_COURSES = [
    # ── Computer Science ──
    {"code": "CSC101", "title": "Introduction to Computer Science", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "CSC201", "title": "Computer Programming I", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "CSC202", "title": "Computer Programming II", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "CSC301", "title": "Data Structures and Algorithms", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "CSC302", "title": "Database Management Systems", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "CSC303", "title": "Operating Systems", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "CSC401", "title": "Software Engineering", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "expert"},
    {"code": "CSC402", "title": "Artificial Intelligence", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "expert"},
    {"code": "CSC403", "title": "Computer Networks", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "expert"},
    {"code": "CSC404", "title": "Cyber Security", "department": "Computer Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "expert"},

    # ── Mathematics ──
    {"code": "MAT101", "title": "General Mathematics I", "department": "Mathematics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "MAT102", "title": "General Mathematics II", "department": "Mathematics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "MAT201", "title": "Linear Algebra", "department": "Mathematics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "MAT202", "title": "Calculus I", "department": "Mathematics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "MAT301", "title": "Calculus II", "department": "Mathematics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "MAT302", "title": "Numerical Analysis", "department": "Mathematics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "MAT303", "title": "Probability and Statistics", "department": "Mathematics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "MAT401", "title": "Operations Research", "department": "Mathematics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "expert"},

    # ── Physics ──
    {"code": "PHY101", "title": "General Physics I", "department": "Physics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "PHY102", "title": "General Physics II", "department": "Physics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "PHY201", "title": "Modern Physics", "department": "Physics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "PHY202", "title": "Electromagnetism", "department": "Physics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "PHY301", "title": "Quantum Mechanics", "department": "Physics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "PHY302", "title": "Thermodynamics", "department": "Physics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},

    # ── Chemistry ──
    {"code": "CHM101", "title": "General Chemistry I", "department": "Chemistry", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "CHM102", "title": "General Chemistry II", "department": "Chemistry", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "CHM201", "title": "Organic Chemistry I", "department": "Chemistry", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "CHM202", "title": "Inorganic Chemistry", "department": "Chemistry", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "CHM301", "title": "Physical Chemistry", "department": "Chemistry", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "CHM302", "title": "Analytical Chemistry", "department": "Chemistry", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},

    # ── Biological Sciences ──
    {"code": "BIO101", "title": "General Biology I", "department": "Biological Sciences", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "BIO102", "title": "General Biology II", "department": "Biological Sciences", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "BIO201", "title": "Genetics", "department": "Biological Sciences", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "BIO202", "title": "Cell Biology", "department": "Biological Sciences", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "BIO301", "title": "Microbiology", "department": "Biological Sciences", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "BIO302", "title": "Biochemistry", "department": "Biological Sciences", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},

    # ── Agricultural Sciences ──
    {"code": "AEC101", "title": "Introduction to Agricultural Economics", "department": "Agricultural Economics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "AEC201", "title": "Farm Management", "department": "Agricultural Economics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "AEC301", "title": "Agricultural Marketing", "department": "Agricultural Economics", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "ANS101", "title": "Animal Science I", "department": "Animal Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "ANS201", "title": "Animal Nutrition", "department": "Animal Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "CPS301", "title": "Crop Production", "department": "Crop Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},
    {"code": "SSC201", "title": "Soil Science", "department": "Soil Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "FST201", "title": "Food Science and Technology", "department": "Food Science", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},

    # ── Engineering ──
    {"code": "ENG101", "title": "Engineering Drawing", "department": "Engineering", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "ENG102", "title": "Engineering Mechanics", "department": "Engineering", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "ENG201", "title": "Fluid Mechanics", "department": "Engineering", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "ENG202", "title": "Thermodynamics for Engineers", "department": "Engineering", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "ENG301", "title": "Strength of Materials", "department": "Engineering", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "advanced"},

    # ── General Studies ──
    {"code": "GST101", "title": "Use of English I", "department": "General Studies", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "GST102", "title": "Use of English II", "department": "General Studies", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "GST103", "title": "Nigerian Peoples and Culture", "department": "General Studies", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "introductory"},
    {"code": "GST201", "title": "Philosophy and Logic", "department": "General Studies", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
    {"code": "GST202", "title": "Entrepreneurship Studies", "department": "General Studies", "university": "Federal University of Agriculture, Abeokuta", "difficulty": "intermediate"},
]

# ── Seeder ────────────────────────────────────────────────────────────────────

def seed_courses():
    """Seed the Course table with FUNAAB courses. Idempotent — skips existing codes."""
    create_db_and_tables()

    with Session(engine) as session:
        # Get existing course codes to avoid duplicates
        existing = session.exec(select(Course.code)).all()
        existing_set = set(existing)

        added = 0
        skipped = 0

        for course_data in FUNAAB_COURSES:
            if course_data["code"] in existing_set:
                skipped += 1
                continue

            course = Course(**course_data)
            session.add(course)
            existing_set.add(course_data["code"])
            added += 1

        session.commit()
        print(f"✅ Seeding complete: {added} courses added, {skipped} already existed.")

    # Verify the count
    with Session(engine) as session:
        total = session.exec(select(Course)).all()
        print(f"📊 Total courses in database: {len(total)}")


if __name__ == "__main__":
    print("🚀 Seeding courses for FUNAAB...")
    seed_courses()
