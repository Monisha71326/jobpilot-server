# JobPilot — free, local-first AI job-search assistant

Search jobs, parse and improve your resume, see **explainable** match scores, write cover letters, track applications on a Kanban board, practise interviews, find skill gaps, and prepare applications with a **review-before-submit** autofill extension.

**Total cost: ₹0.** No paid API, database, hosting, domain, e-mail service or license is required anywhere. AI runs on your own computer through [Ollama](https://ollama.com) (free, open-source models). If your computer can't run a model, every feature still works through deterministic rule-based logic.

> Stack: React + Vite + TypeScript + Tailwind · Django + Django REST Framework · SQLite (default) or PostgreSQL · Ollama · Chrome/Edge MV3 extension.

---

## 1. Quick start (local, no Docker)

Needs Python 3.11+ and Node 20+. Nothing else.

```bash
git clone <your-repo-url> jobpilot && cd jobpilot
bash scripts/setup.sh                 # venv, pip install, migrate, demo jobs, npm install
```

Run in **two terminals**:

```bash
# Terminal 1 – API on http://127.0.0.1:8000
cd backend && .venv/bin/python manage.py runserver

# Terminal 2 – app on http://localhost:5173
cd frontend && npm run dev
```

Open <http://localhost:5173>, register, upload a resume (PDF or DOCX), open **Find jobs**.

Optional: `cd backend && .venv/bin/python manage.py createsuperuser` → then **Admin** appears in the sidebar and Django admin works at <http://127.0.0.1:8000/admin/>.

**Windows (PowerShell) equivalent of setup.sh**

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\pip install -r backend\requirements.txt
copy backend\.env.example backend\.env
cd backend; .venv\Scripts\python manage.py migrate; .venv\Scripts\python manage.py load_demo_jobs; cd ..
cd frontend; npm install; cd ..
```

### PostgreSQL instead of SQLite (optional)

```bash
sudo -u postgres psql -c "CREATE USER jobpilot WITH PASSWORD 'jobpilot';" -c "CREATE DATABASE jobpilot OWNER jobpilot;"
# in backend/.env:
DATABASE_URL=postgres://jobpilot:jobpilot@localhost:5432/jobpilot
cd backend && .venv/bin/python manage.py migrate
```

### Docker Compose (optional; one container serves API + built UI, plus Postgres)

```bash
cp .env.example .env     # then set DJANGO_SECRET_KEY (command is inside the file)
docker compose up --build            # http://localhost:8000
docker compose --profile ollama up   # also runs Ollama in a container (CPU)
```

---

## 2. Free local AI (Ollama)

```bash
bash scripts/check_hardware.sh       # reads RAM/disk/GPU, recommends a model
```

| Your computer | Recommendation |
|---|---|
| < 4 GB RAM | No model. Set `OLLAMA_ENABLED=false`. Rules-only mode. |
| 4–8 GB RAM, CPU only | `llama3.2:3b` (≈2 GB). Try `llama3.2:1b` if slow. |
| 8–16 GB RAM | `llama3.2:3b`; with a GPU/Apple Silicon `qwen2.5:7b` or `llama3.1:8b`. |
| 16 GB+ | `llama3.1:8b` / `qwen2.5:7b`. |

Install (all free):

```bash
curl -fsSL https://ollama.com/install.sh | sh     # Windows/macOS: installer at https://ollama.com/download
ollama pull llama3.2:3b
# backend/.env →  OLLAMA_ENABLED=true   OLLAMA_MODEL=llama3.2:3b
# optional semantic matching:  ollama pull nomic-embed-text   +   OLLAMA_EMBED_MODEL=nomic-embed-text
```

The dashboard banner shows whether the model is reachable. Every AI response is labelled with its engine (`ollama` or `rules`), so you always know what produced it. Model sizes above are approximate and each model has its own licence — check `ollama show <model>` / ollama.com/library before relying on one. Nothing is ever sent to OpenAI, Anthropic, Google or any other hosted AI.

**What uses the LLM vs. plain code**

| Deterministic Python (no AI needed) | Local LLM (falls back to templates/rules) |
|---|---|
| Resume parsing, skill extraction, ATS checks & score | Rewrite suggestions, summary |
| Job match score + explanation factors | Cover letters, recruiter messages |
| Eligibility, duplicate detection, reminders | AI assistant chat |
| Skill-gap analysis, roadmap skeleton | Interview question phrasing & answer feedback |

---

## 3. Features and where to find them

| # | Feature | Where |
|---|---|---|
| 1 | Register / login / logout / profile (token auth, password validators, throttling) | `/register`, `/login`, **Profile & settings** |
| 2 | PDF / DOCX upload + parsing (size/type validated) | **Resumes** → Upload |
| 3 | Resume analysis & suggestions | **Resumes** → Run analysis |
| 4 | Resume builder, 3 templates, versions, export | **Resumes** → open a resume |
| 5 | Job search: role, skill, location, experience, remote | **Find jobs** |
| 6–7 | Matching with factor-by-factor explanation, eligibility notes | job cards / job page |
| 8 | Cover letters & recruiter messages | job page / application page |
| 9 | Kanban tracker, activity log | **Applications** |
| 10 | Saved jobs, reminders (in-app notifications, no e-mail service) | **Saved jobs**, **Reminders** |
| 11 | Interview questions + mock practice with feedback | **Interview practice** |
| 12 | Skill-gap analysis, learning roadmap, career goals | **Skills & roadmap** |
| 13 | AI assistant (uses your profile & resume as context) | **AI assistant** |
| 14–15 | Autofill + review-before-submit | application page → **Prepare**, browser extension |
| 16 | Admin dashboard & Django admin | **Admin** (staff only) |
| 17 | Responsive UI, dark/light | everywhere (checked at 375 px and 1366 px) |
| 18 | Free daily quotas; subscription `Plan` model **disabled** (`BILLING_ENABLED=false`) | **Profile & settings** → usage |

---

## 4. Job data — honest sourcing

`backend/apps/jobs/adapters/` — one adapter per source. Every job stores its **source, original apply URL and last-checked time**.

| Source | Access | Terms we enforce (verified 25 Oct 2026) |
|---|---|---|
| **Remotive** public API | no key | Attribution + link back required; data delayed 24 h; ask ≤ 4×/day, hard limit 2 req/min; must not be re-posted to other job boards. App refresh floor: 6 h. |
| **Arbeitnow** public API | no key | Polite refresh floor: 1 h. |
| **Greenhouse** / **Lever** company boards | public board APIs, you supply a company token | Only the company's own public postings. |
| **Paste a URL / description** | your own content | Parsed locally; links you to the original page. |
| **Demo data** | fictional, labelled `[DEMO]`, no apply link | For testing only. |

LinkedIn, Indeed, Naukri etc. are **not scraped** (no free authorised API, and it would breach their terms). Use *Import job* with the link/description instead. Nothing here bypasses CAPTCHAs or login walls, and no real listing is ever fabricated. To add a source, see `docs/ARCHITECTURE.md`.

---

## 5. Applying safely (autofill extension)

JobPilot **never submits an application for you and never claims one was submitted** until *you* press "I submitted it" in the app.

1. Application page → **Prepare** (eligibility checks, duplicate check, resume choice, cover letter).
2. Read it, then press **I reviewed this**.
3. Chrome/Edge → `chrome://extensions` → Developer mode → **Load unpacked** → select the `extension/` folder.
4. In **Profile & settings** copy your autofill key; paste it and your JobPilot address (`http://127.0.0.1:8000`) into the extension popup. Browser asks permission once for that address only.
5. Open the employer's form → **Fill this page** → check *every* field, attach your resume yourself, solve any CAPTCHA yourself, and submit on the site.
6. Back in JobPilot → **I submitted it** (this explicit confirmation is the only way an application becomes *Applied*). Attempts, which fields were filled, errors, cancel and retry are all logged.

The extension fills only name, e-mail, phone, links, location, headline/summary, years of experience, notice period and the cover letter. It **skips** passwords, file inputs, checkboxes/radios, CAPTCHA, ID numbers, salary, demographic fields, and anything you already typed. It never clicks submit.

---

## 6. Tests

```bash
cd backend && .venv/bin/python manage.py test tests        # 53 tests: auth, authz, parsing, matching, tracking, review gate, SPA
cd frontend && npm run build                                # tsc type-check + production build
```

Verified for this release: all 53 backend tests pass; frontend type-checks and builds; a headless-browser run visited 13 routes at desktop and phone width, clicked 89 buttons, found no console errors, no unexpected API failures and no horizontal overflow; the production path (gunicorn, `DEBUG=false`, built UI) served the UI, assets, deep links, JSON API 404s and admin.

**Not verified here:** the Docker build itself (no Docker daemon in the build sandbox — the compose file passes `docker compose config`), a live Ollama model (no model was installed; the rules path is what ran), live calls to Remotive/Arbeitnow (outbound access was restricted), and the extension against real employer sites (it was written to the rules above but not exercised on third-party pages).

---

## 7. GitHub

```bash
cd jobpilot
git add . && git status          # CHECK: no .env, db.sqlite3, backend/media, node_modules in the list
git commit -m "Initial commit: JobPilot"
# create an EMPTY repo on github.com (free), then:
git remote add origin https://github.com/<you>/jobpilot.git
git branch -M main && git push -u origin main
```

`.gitignore` already excludes `.env*`, SQLite files, `backend/media/` (uploaded resumes), `node_modules` and build output. Use a **private** repo if you keep real data anywhere near it.

---

## 8. Free deployment (optional) → see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

The honest summary: free hosts sleep, have small databases and can't run Ollama. The app is best **run on your own computer**; cloud deployment works in rules-only mode.

## 9. Known limits

- No e-mail/SMS: reminders appear in the in-app bell. (A free SMTP relay would add a dependency with quotas.)
- Scanned/image-only PDFs aren't OCR'd; you'll be told to upload a text PDF or DOCX.
- Match scores are keyword/skill-based (plus optional embeddings) — a guide, not a hiring prediction.
- Autofill is heuristic; sites with unusual or multi-step forms may fill partially. That's why review is mandatory.
- Multi-user hosting of resumes means personal data: use HTTPS, a strong `DJANGO_SECRET_KEY`, and don't invite people you don't intend to be responsible for.
