# Architecture

```
jobpilot/
├── backend/                     Django 5.2 + DRF (token auth)
│   ├── config/                  settings (all env-driven), urls (API, admin, SPA fallback, JSON 404)
│   ├── apps/
│   │   ├── core/                ai.py (Ollama + fallback), quota.py, skills.py/textutil.py, Plan/UsageRecord/Notification
│   │   ├── accounts/            Profile, register/login/logout, autofill key, usage, AI status, notifications
│   │   ├── resumes/             parser.py (PDF/DOCX), analyzer.py (ATS score), builder.py (templates, export), Resume/ResumeVersion
│   │   ├── jobs/                models, matching.py (explainable score), ingest.py, adapters/ (sources), demo-data command
│   │   ├── applications/        Application, ApplicationActivity, Reminder, ApplyAttempt; services.py (eligibility, duplicates, review gate), writing.py
│   │   └── assistant/           chat.py, interview.py, skillgap.py, roles.py; AIConversation/Message, InterviewSession/Answer, CareerGoal
│   ├── tests/                   53 tests (APITestCase; Ollama and job sources are stubbed — no network)
│   ├── requirements.txt  .env.example  entrypoint.sh
├── frontend/                    React 18 + Vite 6 + TS + Tailwind 4 (src/pages, src/components/ui.tsx, src/lib/api.ts)
├── extension/                   MV3 autofill (popup.js talks to /api/autofill/*; filler.js injected only on click)
├── scripts/                     setup.sh, check_hardware.sh
├── docs/                        ARCHITECTURE.md, DEPLOYMENT.md
├── Dockerfile  docker-compose.yml  .env.example
```

## Request flow
Browser → `/api/*` (DRF, `Authorization: Token …`) → app views → deterministic services first → `core.ai.ask()` only where an LLM adds value → every call returns `engine: "ollama" | "rules"`.
In dev Vite proxies `/api` to Django; in production Django serves the built UI (whitenoise) and falls back to `index.html` for client routes, while `/api/*` unknown URLs return JSON 404.

## Data model
`User 1─1 Profile` · `User 1─* Resume 1─* ResumeVersion` · `JobSource 1─* Job` · `(User,Job) → JobMatch` (cached score + factors) · `(User,Job) → SavedJob` · `(User,Job) → Application 1─* ApplicationActivity / Reminder / ApplyAttempt` · `AIConversation 1─* AIMessage` · `InterviewSession 1─* InterviewAnswer` · `CareerGoal` · `Notification` · `UsageRecord (user, feature, day)` · `Plan`.
Uniqueness constraints prevent duplicate applications/saves/usage rows; indexes cover the filtered columns (status, user, day, source).

## Security model
- Every queryset is filtered by `request.user`; other users' objects return **404** (tested). Admin endpoints require `is_staff` (**403** otherwise).
- Resume files are not under a public URL; they download only via `/api/resumes/<id>/file/` after an ownership check. Uploads are validated by extension, size (`MAX_UPLOAD_MB`) and content.
- Autofill key: separate revocable credential that can read autofill data and report results only.
- Throttles on auth and AI endpoints; daily per-feature quotas (`core/quota.py`).
- Production refuses to start without `DJANGO_SECRET_KEY`; cookies/SSL redirect are on unless you opt out for plain-http local runs.

## Application workflow (state machine)
`wishlist → preparing → (review confirmed) → applied → interviewing → offer/rejected`. `applied` can only be reached when the person explicitly sets `confirm_submitted` (the API answers `needs_confirmation` otherwise, and a database check constraint refuses an unconfirmed `applied` row). The autofill endpoint returns nothing until the **review** step is done. `ApplyAttempt` rows record autofill runs (fields filled/skipped, host, error) and support cancel/retry.

## Adding a job source
1. Subclass `JobAdapter` in `backend/apps/jobs/adapters/` and set `slug, name, kind, terms_url, attribution, min_refresh_minutes`.
2. Implement `fetch(query, token) -> list[NormalizedJob]` using `http_json()` (15 s timeout, identifying User-Agent, friendly errors for 404/429).
3. Register it in `adapters/__init__.py`. Only use endpoints whose terms permit it, record the terms URL, and show attribution.

## Subscription architecture (disabled)
`Plan.daily_limits` overrides `DEFAULT_DAILY_LIMITS` per feature. With `BILLING_ENABLED=false` every user gets the default free plan. No payment code exists; adding one later would be a separate integration.
