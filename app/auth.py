from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings
from app.models import User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme — token URL will be our login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Password Helpers ──────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


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
    """Hash a token before storing it in Redis blacklist (never store raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── Redis Blacklist ───────────────────────────────────────────────────────────

def is_token_blacklisted(token: str) -> bool:
    """Check if a refresh token has been revoked. Requires Redis connection."""
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        token_hash = hash_token_for_blacklist(token)
        return r.exists(f"blacklist:{token_hash}") == 1
    except Exception:
        # If Redis is unavailable, fail safe (don't block auth)
        return False


def blacklist_token(token: str, ttl_seconds: int) -> None:
    """Add a refresh token hash to the Redis blacklist with TTL."""
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        token_hash = hash_token_for_blacklist(token)
        r.setex(f"blacklist:{token_hash}", ttl_seconds, "revoked")
    except Exception:
        pass  # Log this in production via Sentry


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
