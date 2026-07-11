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
