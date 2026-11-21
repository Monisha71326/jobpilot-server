"""Persist normalized jobs: upsert, skill/experience extraction, source bookkeeping."""
import hashlib

from django.db import transaction
from django.utils import timezone

from apps.core.skills import extract_skills
from apps.core.textutil import extract_experience_range

from .adapters import ADAPTERS
from .adapters.base import NormalizedJob
from .models import Job, JobSource


def ensure_sources() -> None:
    """Create/update JobSource rows from adapter definitions (idempotent) plus the built-in user/demo sources."""
    for a in ADAPTERS.values():
        JobSource.objects.update_or_create(
            slug=a.slug,
            defaults={"name": a.name, "kind": a.kind, "base_url": a.base_url, "terms_url": a.terms_url,
                      "attribution": a.attribution, "min_refresh_minutes": a.min_refresh_minutes},
        )
    JobSource.objects.get_or_create(slug="user", defaults={"name": "Added by you", "kind": "user", "attribution": "Imported from a link or text you provided."})
    JobSource.objects.get_or_create(slug="demo", defaults={"name": "Demo data", "kind": "demo", "attribution": "Fictional sample jobs for testing the UI. Not real openings."})


def _fields(n: NormalizedJob) -> dict:
    blob = f"{n.title}\n{n.description}"
    lo, hi = extract_experience_range(blob)
    return {
        "title": n.title, "company": n.company, "location": n.location, "is_remote": n.is_remote,
        "employment_type": n.employment_type, "description": n.description, "skills": extract_skills(blob),
        "min_experience": lo, "max_experience": hi, "salary_text": n.salary_text, "apply_url": n.apply_url,
        "posted_at": n.posted_at, "last_checked_at": timezone.now(), "is_active": True,
    }


@transaction.atomic
def upsert_jobs(source: JobSource, items: list[NormalizedJob], *, added_by=None, deactivate_missing_prefix: str = "") -> dict:
    created = updated = 0
    seen: set[str] = set()
    for n in items:
        if not n.title or not n.external_id:
            continue
        seen.add(n.external_id)
        obj, was_created = Job.objects.update_or_create(
            source=source, external_id=n.external_id, added_by=added_by, defaults=_fields(n)
        )
        created += was_created
        updated += not was_created
    deactivated = 0
    if deactivate_missing_prefix:
        qs = Job.objects.filter(source=source, added_by__isnull=True, external_id__startswith=deactivate_missing_prefix, is_active=True)
        deactivated = qs.exclude(external_id__in=seen).update(is_active=False)
    return {"created": created, "updated": updated, "deactivated": deactivated}


def external_id_for(n: NormalizedJob) -> str:
    key = (n.apply_url or "").split("#")[0] or f"{n.title}|{n.company}|{n.description[:500]}"
    return hashlib.sha1(key.encode()).hexdigest()[:40]


DEMO = [
    ("Junior Python Backend Developer", "Python, Django, REST APIs, PostgreSQL and Git. 0-2 years of experience. Build and test API endpoints, write unit tests with pytest, and work in an Agile team.", "Chennai, India", False),
    ("Full-Stack Engineer (React + Django)", "3+ years of experience with React, TypeScript, Django REST Framework, PostgreSQL, Docker and CI/CD. You will own features end to end and mentor juniors.", "Bengaluru, India", False),
    ("Remote Frontend Developer", "React, TypeScript, Tailwind CSS, HTML, CSS and testing with Jest. 2-4 years of experience. Fully remote, async-friendly team. Strong communication skills.", "Remote", True),
    ("Data Analyst", "SQL, Excel, Python, Pandas, Tableau and data visualization. 1-3 years experience. Build dashboards and present insights to stakeholders.", "Hyderabad, India", False),
    ("Machine Learning Engineer", "Python, PyTorch, scikit-learn, NLP, LLMs, Docker and AWS. 3-5 years of experience deploying models to production.", "Remote", True),
    ("DevOps Engineer", "Linux, Docker, Kubernetes, Terraform, AWS, CI/CD and monitoring. 4+ years of experience with production systems.", "Pune, India", False),
    ("Customer Support Associate", "Customer support, communication, Excel and helpdesk tools. Freshers welcome. Rotational shifts.", "Chennai, India", False),
    ("QA Automation Engineer", "Selenium, Playwright, pytest, Python, Jira and CI/CD. 2+ years of test automation experience.", "Remote", True),
]


def load_demo_jobs() -> dict:
    """Load clearly-labelled FICTIONAL jobs so the UI can be tried offline. Idempotent."""
    from datetime import timedelta

    ensure_sources()
    source = JobSource.objects.get(slug="demo")
    now = timezone.now()
    items = [
        NormalizedJob(
            external_id=f"demo-{i}", title=f"[DEMO] {t}", company="Example Corp (fictional)", description=d,
            location=loc, is_remote=rem, apply_url="", posted_at=now - timedelta(days=i),
        )
        for i, (t, d, loc, rem) in enumerate(DEMO)
    ]
    return upsert_jobs(source, items)
