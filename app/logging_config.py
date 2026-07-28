"""
Observability Stack [E008-S05]
- Structured JSON logging with correlation IDs for request tracing
- Sentry integration for real-time error tracking
"""
import logging
import json
import uuid
from datetime import datetime, timezone
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Correlation ID context variable — flows through async boundaries
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that injects a correlation ID into every request.
    - Reads x-correlation-id from the request header if provided (for distributed tracing)
    - Generates a new UUID otherwise
    - Makes it available via the correlation_id_var context variable
    - Adds it to the response headers
    """

    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("x-correlation-id", str(uuid.uuid4()))
        correlation_id_var.set(cid)

        response = await call_next(request)

        # Set correlation ID in response headers for client-side tracing
        response.headers["X-Correlation-ID"] = cid
        return response


class JSONLogFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    Includes: timestamp, level, logger, message, correlation_id, and extra fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get() or "",
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra context added via extra={}
        if hasattr(record, "extra") and record.extra:
            log_entry["extra"] = record.extra

        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure root logger with JSON output format."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JSONLogFormatter())
    logger.addHandler(handler)

    # Set specific logger levels
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name, pre-configured for JSON output."""
    return logging.getLogger(name)
