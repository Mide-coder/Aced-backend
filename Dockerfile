"""
Multi-stage Dockerfile [E008-S01]
Optimized for Render/Railway free tiers (512MB RAM)
- Stage 1: Build dependencies
- Stage 2: Runtime — minimal image
- No persistent sessions or raw SQL strings

Build:      docker build -t aced-api .
Run:        docker run -p 8000:8000 --env-file .env aced-api
"""

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Set build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /build

# Copy dependency files first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies into a local .venv
RUN uv sync --locked --no-dev

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Set runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=production

# Install runtime system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN addgroup --system --gid 1001 aced && \
    adduser --system --uid 1001 --gid 1001 aced

# Copy virtual environment from builder
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . /app/

# Set ownership to non-root user
RUN chown -R aced:aced /app

# Switch to non-root user
USER aced

# Set working directory
WORKDIR /app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn — optimized for 512MB RAM
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--limit-concurrency", "100"]
