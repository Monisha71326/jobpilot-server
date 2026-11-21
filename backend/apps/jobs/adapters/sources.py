"""Concrete adapters. Each hits only an official, documented, public endpoint."""
import html
from datetime import datetime, timezone

from apps.core.textutil import clean_html

from .base import JobAdapter, NormalizedJob, http_json


def _dt(value):
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, tz=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc) if "T" in str(value) else datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class RemotiveAdapter(JobAdapter):
    """https://remotive.com/api/remote-jobs - free public API.

    Remotive's published rules (checked Oct 2026): fetch at most ~4x/day, <=2 requests/min, name Remotive as the
    source and link back, do not republish jobs to third-party job boards. We therefore enforce a 6h refresh floor,
    show attribution and always link to the original Remotive page.
    """

    slug, name, kind = "remotive", "Remotive", "api"
    base_url = "https://remotive.com"
    terms_url = "https://github.com/remotive-com/remote-jobs-api"
    attribution = "Jobs via Remotive (remotive.com). Data may be delayed 24h; apply on the original page."
    min_refresh_minutes = 360

    def fetch(self, *, query="", token=""):
        params = {"limit": 100}
        if query:
            params["search"] = query[:80]
        data = http_json("https://remotive.com/api/remote-jobs", params)
        out = []
        for j in data.get("jobs", []):
            out.append(NormalizedJob(
                external_id=str(j.get("id")), title=j.get("title", "")[:200], company=j.get("company_name", "")[:160],
                description=clean_html(j.get("description", "")), location=(j.get("candidate_required_location") or "Remote")[:160],
                is_remote=True, employment_type=(j.get("job_type") or "").replace("_", " ")[:40], salary_text=(j.get("salary") or "")[:120],
                apply_url=j.get("url", ""), posted_at=_dt(j.get("publication_date")),
            ))
        return out


class ArbeitnowAdapter(JobAdapter):
    """https://www.arbeitnow.com/api/job-board-api - free, no key. No published rate limit; we stay polite (1/hour)."""

    slug, name, kind = "arbeitnow", "Arbeitnow", "api"
    base_url = "https://www.arbeitnow.com"
    terms_url = "https://arbeitnow.com/blog/job-board-api/"
    attribution = "Jobs via Arbeitnow (arbeitnow.com). Apply on the original page."
    min_refresh_minutes = 60

    def fetch(self, *, query="", token=""):
        data = http_json("https://www.arbeitnow.com/api/job-board-api")
        out, q = [], query.lower().strip()
        for j in data.get("data", []):
            n = NormalizedJob(
                external_id=str(j.get("slug")), title=j.get("title", "")[:200], company=j.get("company_name", "")[:160],
                description=clean_html(j.get("description", "")), location=(j.get("location") or "")[:160],
                is_remote=bool(j.get("remote")), employment_type=", ".join(j.get("job_types") or [])[:40],
                apply_url=j.get("url", ""), posted_at=_dt(j.get("created_at")),
            )
            if not q or q in f"{n.title} {n.company} {n.description[:600]}".lower():
                out.append(n)
        return out


class GreenhouseAdapter(JobAdapter):
    """Greenhouse public Job Board API (GET, no key): boards-api.greenhouse.io/v1/boards/{token}/jobs. Needs a company board token."""

    slug, name, kind = "greenhouse", "Greenhouse company boards", "board"
    base_url = "https://boards.greenhouse.io"
    terms_url = "https://developers.greenhouse.io/job-board.html"
    attribution = "Jobs from the company's public Greenhouse job board."
    min_refresh_minutes = 60
    needs_board_token = True
    full_listing = True

    def fetch(self, *, query="", token=""):
        data = http_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", {"content": "true"})
        out = []
        for j in data.get("jobs", []):
            loc = (j.get("location") or {}).get("name", "")
            out.append(NormalizedJob(
                external_id=f"{token}:{j.get('id')}", title=j.get("title", "")[:200], company=token.replace("-", " ").title()[:160],
                description=clean_html(html.unescape(j.get("content", ""))), location=loc[:160], is_remote="remote" in loc.lower(),
                apply_url=j.get("absolute_url", ""), posted_at=_dt(j.get("updated_at")),
            ))
        return out


class LeverAdapter(JobAdapter):
    """Lever public Postings API (GET, no key): api.lever.co/v0/postings/{company}?mode=json."""

    slug, name, kind = "lever", "Lever company boards", "board"
    base_url = "https://jobs.lever.co"
    terms_url = "https://github.com/lever/postings-api"
    attribution = "Jobs from the company's public Lever postings page."
    min_refresh_minutes = 60
    needs_board_token = True
    full_listing = True

    def fetch(self, *, query="", token=""):
        data = http_json(f"https://api.lever.co/v0/postings/{token}", {"mode": "json"})
        out = []
        for j in data if isinstance(data, list) else []:
            cats = j.get("categories") or {}
            loc = cats.get("location", "") or ""
            out.append(NormalizedJob(
                external_id=f"{token}:{j.get('id')}", title=j.get("text", "")[:200], company=token.replace("-", " ").title()[:160],
                description=(j.get("descriptionPlain") or clean_html(j.get("description", ""))), location=loc[:160],
                is_remote=(j.get("workplaceType") == "remote") or "remote" in loc.lower(),
                employment_type=(cats.get("commitment") or "")[:40], apply_url=j.get("applyUrl") or j.get("hostedUrl", ""),
                posted_at=_dt(j.get("createdAt")),
            ))
        return out
