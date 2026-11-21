# Free deployment notes

Checked against vendors' own pages on **25 Oct 2026**. Free tiers change — re-read the linked page before you deploy, and never add a card you don't want charged.

## Recommended: run it on your own computer (₹0, no limits)
Local mode keeps resumes on your disk and lets Ollama run. Everything in the README works.

## Option A — one free web service + free Postgres

The Dockerfile builds the UI and serves UI + API from one Django process, so you need only **one** web service.

| Piece | Free service | Verified limits | Consequence for JobPilot |
|---|---|---|---|
| Web app | **Render** free web service ([docs](https://render.com/docs/free)) | Sleeps after 15 min idle (~1 min wake-up); 750 instance-hours/month per workspace, then suspended until next month; **ephemeral disk**; outbound SMTP ports blocked; "may be restarted at any time". | First request after idle is slow. Uploaded resume *files* vanish on restart/redeploy. Parsed text, analysis and builder content are stored in the database and survive. No e-mail needed by design. |
| Database | **Neon** free Postgres ([limits](https://neon.com/faqs/free-plan-limits-and-quotas)) | 1 GB per project; 100 CU-hours/month; compute scales to zero after 5 min (cannot be disabled); no overage billing on Free (writes fail at the limit). The page doesn't state whether a card is required — check at sign-up. | Plenty for personal use; first query after idle is slower. |
| AI | none | Ollama can't run on free web tiers. | Set `OLLAMA_ENABLED=false`: rule-based mode. |

**Don't use Render's own free Postgres for anything you want to keep:** Render's docs say free databases **expire 30 days after creation** (then a 14-day grace period before deletion), with no backups.

Environment variables to set on the service (never commit them):

```
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<python3 -c "import secrets;print(secrets.token_urlsafe(50))">
DJANGO_ALLOWED_HOSTS=<your-app>.onrender.com
CORS_ALLOWED_ORIGINS=https://<your-app>.onrender.com
DATABASE_URL=<Neon connection string, sslmode=require>
OLLAMA_ENABLED=false
BILLING_ENABLED=false
```

Build: **Docker** (root `Dockerfile`; its entrypoint runs migrations and `collectstatic`). No custom domain is needed — you get a free `*.onrender.com` HTTPS URL. Then create an admin from the host's shell if available, or temporarily run `createsuperuser` locally against the same `DATABASE_URL`.

**Before inviting others:** HTTPS is automatic on that URL; resumes are personal data; the browser extension's host list covers only `localhost:8000`, so for a hosted URL the extension asks for permission to that origin at connect time.

## Option B — nothing hosted
Share nothing; use locally. This is the only option with zero caveats.

## Not verified
I could not load Cloudflare Pages' limits page from the build environment, so it is **not** recommended here. If you want a separate static frontend host, read its current terms first; the API base would also need a CORS entry in `CORS_ALLOWED_ORIGINS`.
