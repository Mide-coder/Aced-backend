"""
Security Audit — Encryption at Rest [E008-S01]
===============================================
SQLAlchemy TypeDecorator for transparent encryption/decryption of sensitive fields.

Uses Fernet symmetric encryption from the cryptography library.
Data is encrypted before being stored in the database and decrypted when read.

Usage:
    from app.encryption import EncryptedString

    class User(SQLModel, table=True):
        __tablename__ = "users"
        ...
        phone = Field(sa_column=Column(EncryptedString(255)), default=None)

Requirements:
    - Set ENCRYPTION_KEY in .env (generated via `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
    - cryptography package (already included via python-jose[cryptography])
"""

import os
import logging
from sqlalchemy.types import TypeDecorator, String
from cryptography.fernet import Fernet

logger = logging.getLogger("aced.encryption")


def _get_fernet() -> Fernet | None:
    """Get a Fernet instance from the ENCRYPTION_KEY environment variable."""
    key = os.getenv("ENCRYPTION_KEY", "")
    if not key:
        logger.warning("ENCRYPTION_KEY not set — sensitive fields will be stored as plaintext")
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        logger.error("Invalid ENCRYPTION_KEY: %s", str(e))
        return None


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy TypeDecorator that transparently encrypts/decrypts string fields.

    Stores data as a VARBINARY (encrypted) in the database.
    Presents as a str in Python code.

    Example:
        from sqlalchemy import Column
        from app.encryption import EncryptedString

        class User(SQLModel, table=True):
            ssn = Field(sa_column=Column(EncryptedString(512)), default=None)
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 255):
        super().__init__(length)
        self.fernet = _get_fernet()

    def process_bind_param(self, value: str | None, dialect) -> bytes | None:
        """Encrypt the value before storing."""
        if value is None:
            return None
        if self.fernet is None:
            return value  # Fallback: store as plaintext
        return self.fernet.encrypt(value.encode("utf-8"))

    def process_result_value(self, value: bytes | None, dialect) -> str | None:
        """Decrypt the value when reading."""
        if value is None:
            return None
        if self.fernet is None:
            return value  # Fallback: return as-is (plaintext)
        try:
            return self.fernet.decrypt(value).decode("utf-8")
        except Exception as e:
            logger.error("Failed to decrypt value: %s", str(e))
            return None
