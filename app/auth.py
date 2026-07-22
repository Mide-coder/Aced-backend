from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib

from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.config import settings

# OAuth2 scheme — token URL will be our login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Password Helpers ──────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ── Token Helpers ─────────────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    """Create a short-lived access token (15 min)."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a long-lived refresh token (7 days)."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload.update({"exp": expire, "type": "refresh"})
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def hash_token_for_blacklist(token: str) -> str:
    """Hash a token before storing it in database (never store raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── Database Blacklist ────────────────────────────────────────────────────────

def is_token_blacklisted(token: str, session: Session) -> bool:
    """Check if a refresh token has been revoked."""
    from app.models import TokenBlacklist
    
    token_hash = hash_token_for_blacklist(token)
    result = session.exec(
        select(TokenBlacklist).where(TokenBlacklist.token_hash == token_hash)
    ).first()
    return result is not None


def blacklist_token(token: str, expires_at: datetime, session: Session) -> None:
    """Add a refresh token hash to the database blacklist."""
    from app.models import TokenBlacklist
    
    token_hash = hash_token_for_blacklist(token)
    
    # Check if already blacklisted (idempotency)
    existing = session.exec(
        select(TokenBlacklist).where(TokenBlacklist.token_hash == token_hash)
    ).first()
    
    if existing:
        return  # Already blacklisted
    
    blacklist_entry = TokenBlacklist(
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(blacklist_entry)
    session.commit()


# ── Current User Dependency ───────────────────────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency — extracts and validates the current user from JWT."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    return payload
