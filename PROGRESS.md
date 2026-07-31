# Aced — Progress Audit (last updated 2026-07-31)

State of the `feature/scaffolding` branch. All work below is committed; 3 commits were pushed to `origin/feature/scaffolding` on this date.

## ✅ DONE — backend (complete)
- **Auth**: JWT access (15 min) + refresh (7d) tokens, register (university auto-detect), login, refresh, logout, me
- **Models**: User, TutorProfile, Course, Booking, Review, Payment, Availability, Ledger
- **Routers**: auth, tutors (search w/ GIN indexes, profile, reviews), bookings (CRUD + escrow state machine), payments (Paystack webhook, idempotency), media (Cloudflare R2 upload), admin (verification, grade verify, payout ledger), public (tutor profile pages)
- **Infra**: pydantic-settings config (.env), JSON logging w/ correlation IDs, at-rest encryption TypeDecorator, identity verification workflow, Celery Beat + Redis for WhatsApp reminders, SQLite/Postgres switching, 54 FUNAAB courses seeded
- **Commit refs**: `ab5ce2d` (Sprint 1-4 backend), `f147ef6` + earlier (escrow/payments), `81dbc44` (new endpoints + seed data)

## ✅ DONE — frontend (complete, all wired to API)
- Pages: `index.html`, `landing.html`, `auth.html`, `dashboard.html`, `tutor-dashboard.html`, `booking.html`, `admin.html`, `payment-callback.html`, `app/templates/tutor_profile.html` + `api.js` client (all endpoints, token mgmt, error handling)
- Dashboards + booking flow + payment callback connected to real API (`81dbc44`)
- **Email login/register fixed** — `auth.html` now calls the real API (was "waiting for backend integration"); register auto-logs-in, role-based redirect (`71bf629`)
- **Google sign-in implemented end-to-end** — backend `POST /auth/google` (verifies ID token via google-auth, email_verified guard, create-or-login) + `GET /auth/google-config`; frontend uses Google Identity Services with race/stale-role/re-init guards (`71bf629`)
- **Sentry DSN configured** in `.env` (`350fcf7` — config ignores empty env vars)

## ⏸ PAUSED — needs user input
1. **`GOOGLE_CLIENT_ID` is NOT set** — Google button is wired but dormant. User must create an OAuth Client ID in Google Cloud Console (Web application; **Authorized JavaScript origin: `http://localhost:3000`**) and paste it. Then: add to `.env`, restart backend, verify Google login in browser.
2. **Cloudflare R2 keys NOT set** — media uploads will fail until `R2_*` env vars are added (bucket + keys).

## 🔜 NEXT — priority order
1. Verify demo data: check tutors/profiles/courses/reviews exist (commit `81dbc44` included seed data); register a tutor via auth.html if the search returns empty
2. **401 token-refresh interceptor** in `api.js` — access token expires in 15 min; without it all API calls fail after that
3. `payment-callback.html` — verify real booking status via `GET /bookings/{id}` instead of client-side only
4. Add `GET /courses` endpoint so admin can list courses properly
5. Seed more universities (UNILAG, UI, OAU) in `seed_courses.py`
6. UptimeRobot ping to keep Render/Railway free tier awake
7. Deploy to Render + set env vars: `DATABASE_URL`, `SENTRY_DSN`, `PAYSTACK_SECRET`, `GOOGLE_CLIENT_ID`, `R2_*`, `JWT_SECRET`

## 🔑 Commands (Windows)
- Backend: `./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001` (log: `backend.log`)
- Frontend: `python -m http.server 3000`
- Seed: `./.venv/Scripts/python.exe seed_courses.py`
- API docs: `http://localhost:8001/docs` · Health: `http://localhost:8001/health`

## 👤 Local test accounts (created during testing, dev DB only)
- `demo.student@funaab.edu.ng` / `Demo@1234` (student)
- `buffy.test@funaab.edu.ng` / `Demo@1234` (student)
- `google.ready@funaab.edu.ng` / `Demo@1234` (tutor)
