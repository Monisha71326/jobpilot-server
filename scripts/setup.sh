#!/usr/bin/env bash
# One-time local setup (Linux/macOS/WSL). Uses SQLite by default - no database server needed.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
[ -f backend/.env ] || { cp backend/.env.example backend/.env; echo "Created backend/.env (git-ignored)"; }
(cd backend && .venv/bin/python manage.py migrate && .venv/bin/python manage.py load_demo_jobs)
(cd frontend && npm install)
cat <<MSG

Done. Run in two terminals:
  Terminal 1:  cd backend  && .venv/bin/python manage.py runserver     # API on :8000
  Terminal 2:  cd frontend && npm run dev                              # app on http://localhost:5173
Make an admin:  cd backend && .venv/bin/python manage.py createsuperuser
AI model advice: bash scripts/check_hardware.sh
MSG
