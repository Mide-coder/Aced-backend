"""
Celery Beat Configuration [E004-S04]
WhatsApp Notifications via Celery Beat with Redis broker (Upstash Free Tier)

This module configures Celery for scheduled reminder tasks:
- 24h before session: reminder to student
- 1h before session: reminder to student
"""

import os
from celery import Celery

# Redis broker URL (configure Upstash Free Tier Redis URL in .env)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aced",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],
)

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    "session-reminder-24h": {
        "task": "app.tasks.send_session_reminder_24h",
        "schedule": 3600.0,  # Check every hour
    },
    "session-reminder-1h": {
        "task": "app.tasks.send_session_reminder_1h",
        "schedule": 1800.0,  # Check every 30 minutes
    },
}

celery_app.conf.timezone = "Africa/Lagos"
