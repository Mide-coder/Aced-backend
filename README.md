<div align="center">
  <img src="https://img.shields.io/badge/status-production-ready-green" alt="Status">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-MIT-purple" alt="License">
  <br>
  <h1>🎓 Aced API</h1>
  <p><strong>University Tutoring Platform — Connect students with verified tutors</strong></p>
  <p>A stateless, secure backend for matching Nigerian university students with qualified tutors, managing escrow payments, and facilitating academic support.</p>
</div>

---

## ✨ Features

| Area | Capabilities |
|------|-------------|
| **🔐 Authentication** | Dual-role (Student/Tutor) JWT auth with university auto-detection from email domains. Rotating refresh tokens with database blacklist. |
| **👨‍🏫 Tutor Discovery** | Fuzzy course code search (e.g., "CSC201" ↔ "CSC 201") with filters for price (₦1,000–₦5,000), rating, and verified status. |
| **💳 Escrow Payments** | Rigid state machine (Pending → Paid Escrow → Completed → Funds Released) with Paystack webhook integration and idempotency keys. |
| **✅ Verified A Badge** | Manual grade verification workflow — tutors who prove their "A" grades earn the trust marker. |
| **📹 Media Uploads** | Stateless uploads to Cloudflare R2 with UUID filenames — zero PII exposure in storage paths. |
| **📱 Session Reminders** | Celery Beat + Redis for automated WhatsApp reminders 24h and 1h before sessions. |
| **📊 Public Profiles** | SEO-optimized tutor profile pages with Open Graph meta tags for rich link previews on WhatsApp, Twitter, and Telegram. |
| **🛡️ Security Hardened** | Rate limiting (SlowAPI), structured JSON logging with correlation IDs, Sentry error tracking, and optional encryption at rest. |
| **💰 Financial Ledger** | Double-entry bookkeeping for tracking completed sessions and manual bank transfers to tutors. |

---

## 🏗 Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Frontend   │────▶│  Aced API    │────▶│  PostgreSQL  │
│  (React)    │     │  (FastAPI)   │     │  (SQLite*)   │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────┴───────┐      ┌─────────────┐
                    │  Background  │─────▶│  Redis       │
                    │  Workers     │      │  (Upstash)   │
                    │  (Celery)    │      └─────────────┘
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │  File Store  │
                    │  (R2)        │
                    └──────────────┘
```

*<sup>SQLite for local development, PostgreSQL for production deployments.</sup>*

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+** — [Download](https://www.python.org/downloads/)
- **uv** — Install with `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/Mide-coder/Aced-backend.git
cd Aced-backend

# 2. Configure environment
cp .env.example .env

# 3. Install dependencies
uv sync

# 4. Seed the database with 50+ FUNAAB courses
uv run python seed_courses.py

# 5. Start the development server
uv run uvicorn main:app --reload
```

Your API is now live at **http://localhost:8000**.
Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## 📋 API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Create account (auto-detects university from email) |
| `POST` | `/auth/login` | Sign in — returns access + refresh tokens |
| `POST` | `/auth/refresh` | Rotate refresh token (7-day TTL) |
| `POST` | `/auth/logout` | Revoke refresh token |
| `GET` | `/auth/me` | Get authenticated user's profile |

### Tutors & Discovery
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tutors/search` | Search tutors by course, price, rating |
| `GET` | `/tutors/{id}` | Get full tutor profile with courses |
| `POST` | `/tutors/profile` | Create tutor profile |
| `GET` | `/tutors/{id}/reviews` | Get tutor reviews |
| `GET` | `/public/tutors/{id}` | Public HTML profile (SEO/OG enabled) |

### Media & Verification
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/media/upload/demo-video` | Upload tutor demo video (R2) |
| `POST` | `/media/upload/matric-id` | Upload matric ID for verification |

### Bookings & Availability
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/bookings/` | Create a booking (state: Pending) |
| `PATCH` | `/bookings/{id}/status` | Update booking status (state machine enforced) |
| `POST` | `/bookings/{id}/cancel` | Cancel booking (handles 20% deposit logic) |
| `GET` | `/bookings/my-bookings` | List current user's bookings |
| `POST` | `/bookings/availability` | Set recurring availability |
| `GET` | `/bookings/availability/{tutor_id}` | Get tutor's available slots |

### Payments
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/payments/initialize` | Initialize Paystack payment |
| `POST` | `/payments/paystack-webhook` | Paystack webhook handler |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| `PATCH` | `/admin/tutors/{id}/grade-verify` | Toggle "Verified A" badge |
| `GET` | `/admin/verification-requests` | List identity verification requests |
| `PATCH` | `/admin/verification-requests/{id}` | Review & approve/reject verification |
| `GET` | `/admin/payout-ledger` | View financial payout ledger |
| `POST` | `/admin/payout-ledger/{id}/record-payout` | Record tutor payout |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check (use for uptime monitoring) |

---

## 🔧 Configuration

All configuration is managed through environment variables (`.env`). Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite:///./aced.db` |
| `JWT_SECRET` | JWT signing key | `change-me-in-production` |
| `PAYSTACK_SECRET` | Paystack API secret | — |
| `SENTRY_DSN` | Sentry error tracking DSN | — |
| `R2_*` | Cloudflare R2 credentials | — |
| `REDIS_URL` | Redis connection (Celery) | `redis://localhost:6379/0` |

---

## 🐳 Docker

```bash
# Build the image
docker build -t aced-api .

# Run with env file
docker run -p 8000:8000 --env-file .env aced-api
```

---

## ☁️ Deployment

This project is pre-configured for **Render** via `render.yaml`:

1. Push the repo to GitHub
2. Connect your repository to [Render](https://render.com)
3. Render auto-detects the `render.yaml` blueprint
4. Set the required environment variables in Render's dashboard

### ⏰ Uptime Protection

Free-tier Render/Railway services spin down after 15 minutes of inactivity.
Set up [UptimeRobot](https://uptimerobot.com) to ping `/health` every 14 minutes to keep the service awake.

---

## 🛡️ Security

- **Stateless JWTs** — 15-minute access tokens, 7-day rotating refresh tokens
- **Password Hashing** — bcrypt with salt rounds
- **Rate Limiting** — 5 login attempts per 15 minutes per IP; 100 global requests per minute
- **Input Validation** — All endpoints use Pydantic schemas
- **Encryption at Rest** — Optional Fernet symmetric encryption for sensitive fields
- **Error Tracking** — Sentry integration for real-time 500-series alerts
- **NDPR Compliant** — No PII in logs or URLs; UUID-based storage filenames

---

## 📊 Tech Stack

| Category | Technology |
|----------|-----------|
| **Framework** | FastAPI 0.115 |
| **ORM** | SQLModel (SQLAlchemy + Pydantic) |
| **Auth** | python-jose (JWT) + bcrypt |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Migrations** | Alembic |
| **Cache/Queue** | Redis (Upstash) |
| **Task Queue** | Celery |
| **File Storage** | Cloudflare R2 (S3-compatible) |
| **Payments** | Paystack |
| **Monitoring** | Sentry |
| **Rate Limiting** | SlowAPI |
| **Templates** | Jinja2 |

---

## 🧩 Project Structure

```
aced-backend/
├── main.py                  # Application entry point
├── seed_courses.py          # Database seeder (50+ courses)
├── Dockerfile               # Multi-stage production build
├── render.yaml              # Render deployment config
├── .env.example             # Environment template
├── requirements.txt         # Pinned dependencies
├── app/
│   ├── __init__.py
│   ├── config.py            # pydantic-settings configuration
│   ├── database.py          # Database engine & session
│   ├── models.py            # SQLModel table definitions
│   ├── auth.py              # JWT creation, validation, password helpers
│   ├── rate_limit.py        # SlowAPI rate limiter
│   ├── logging_config.py    # JSON logging + correlation IDs
│   ├── encryption.py        # SQLAlchemy TypeDecorator for encryption
│   ├── verification.py      # Identity validation criteria
│   ├── celery_app.py        # Celery configuration
│   ├── tasks.py             # Background tasks (WhatsApp reminders)
│   ├── templates/           # Jinja2 templates
│   │   └── tutor_profile.html
│   └── routers/
│       ├── auth.py          # Register, login, refresh, logout
│       ├── tutors.py        # Search, profiles, reviews
│       ├── media.py         # File upload endpoints
│       ├── bookings.py      # Booking CRUD, availability, state machine
│       ├── payments.py      # Paystack integration
│       ├── admin.py         # Verification, grade-verify, payout ledger
│       └── public.py        # Public tutor profiles (HTML)
```

---

## 💰 Zero-Cost Architecture

This platform is designed to run on free tiers:

| Service | Free Tier | Purpose |
|---------|-----------|---------|
| Render | 512MB RAM | API hosting |
| Upstash | 256MB Redis | Celery broker |
| Cloudflare R2 | 10GB storage | File uploads |
| Sentry | 5,000 events/mo | Error tracking |
| UptimeRobot | 50 monitors | Uptime monitoring |
| Paystack | Test mode | Payment processing |

---

## 👥 Team

| Role | Name |
|------|------|
| **Lead Backend** | Safari |
| **Integration** | Sanumi |
| **Strategy & Ops** | Mide |

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <sub>Built with ❤️ for Nigerian university students</sub>
</div>
