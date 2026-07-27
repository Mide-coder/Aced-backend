from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from datetime import timezone, datetime

from app.database import get_session
from app.models import User, UserCreate, UserRead, detect_university_from_email
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    blacklist_token,
    is_token_blacklisted,
    get_current_user,
)
from app.config import settings
from app.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")  # 10 registrations per minute per IP
def register(request: Request, user_in: UserCreate, session: Session = Depends(get_session)):
    """
    Register a new user.
    - University is auto-detected from email domain (e.g. @funaab.edu.ng)
    - Role defaults to 'student' unless specified
    """
    # Check if email already exists
    existing = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Auto-detect university from email domain
    university = detect_university_from_email(user_in.email)
    if university is None:
        # Allow registration but flag as unverified external user
        university = None  # Will require manual verification

    new_user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        role=user_in.role,
        university=university,
        hashed_password=hash_password(user_in.password),
        is_verified=university is not None,  # auto-verify known university emails
    )

    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return new_user


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login")
@limiter.limit("5/15minutes")  # 5 login attempts per 15 minutes per IP
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """
    Login with email + password.
    Returns access token (15 min) and refresh token (7 days).
    """
    user = session.exec(select(User).where(User.email == form_data.username)).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    token_data = {"sub": str(user.id), "role": user.role, "email": user.email}

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ── Refresh Token Rotation ────────────────────────────────────────────────────

@router.post("/refresh")
@limiter.limit("10/minute")  # 10 refresh attempts per minute per IP
def refresh_token(request: Request, refresh_token: str, session: Session = Depends(get_session)):
    """
    Rotate refresh token.
    - Validates the old refresh token
    - Checks it hasn't been blacklisted (revoked)
    - Issues new access + refresh tokens
    - Blacklists the old refresh token (rotation)
    """
    # Check blacklist first
    if is_token_blacklisted(refresh_token, session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    # Decode and validate
    payload = decode_token(refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Calculate expiration datetime for blacklist entry
    exp_timestamp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

    # Blacklist the old refresh token (rotation — old token is now invalid)
    blacklist_token(refresh_token, expires_at, session)

    # Issue new token pair
    token_data = {
        "sub": payload.get("sub"),
        "role": payload.get("role"),
        "email": payload.get("email"),
    }

    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    refresh_token: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Logout — blacklists the refresh token so it can't be used again.
    Access token expires naturally after 15 min.
    """
    if is_token_blacklisted(refresh_token, session):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token already revoked",
        )

    payload = decode_token(refresh_token)
    exp_timestamp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

    blacklist_token(refresh_token, expires_at, session)


# ── Me (current user info) ────────────────────────────────────────────────────

@router.get("/me", response_model=UserRead)
def get_me(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get currently authenticated user's profile."""
    user = session.exec(
        select(User).where(User.id == int(current_user["sub"]))
    ).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user
