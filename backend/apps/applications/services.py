"""Application business rules: duplicate detection, resume selection, eligibility, reminders, activity log."""
from datetime import timedelta

from django.utils import timezone

from apps.core.models import Notification
from apps.jobs import matching
from apps.resumes.models import Resume

from .models import Application, ApplicationActivity, Reminder


def log(app: Application, kind: str, message: str, **meta) -> None:
    ApplicationActivity.objects.create(application=app, kind=kind, message=message[:400], meta=meta)


def find_duplicate(user, *, job=None, title="", company="", location="") -> Application | None:
    """Same job row, or the same posting (title+company+location) seen via another source/manual entry."""
    from apps.jobs.models import normalize_fp

    if job is not None:
        hit = Application.objects.filter(user=user, job=job).first()
        if hit:
            return hit
        title, company, location = job.title, job.company, job.location
    return Application.objects.filter(user=user, fingerprint=normalize_fp(title, company, location)).first()


def choose_resume(user, job) -> tuple[Resume | None, dict]:
    """Pick the user's resume with the best match for this job, and explain why."""
    resumes = list(Resume.objects.filter(user=user))
    if not resumes:
        return None, {"reason": "You have no resume yet."}
    if len(resumes) == 1 or job is None:
        r = next((x for x in resumes if x.is_primary), resumes[0])
        return r, {"reason": "Your primary resume." if job is None else "Your only resume."}
    scored = []
    for r in resumes:
        m = matching.ensure_matches(user, r, [job]).get(job.id)
        scored.append((m.score if m else 0, r))
    scored.sort(key=lambda t: (-t[0], not t[1].is_primary))
    best = scored[0]
    return best[1], {"reason": f"Best match for this job ({best[0]}%)", "scores": [{"resume_id": r.id, "title": r.title, "score": s} for s, r in scored]}


def eligibility(user, app: Application) -> dict:
    """Pre-submission checklist. Warnings never silently block - the person decides - but they must be acknowledged."""
    checks, warnings = [], []
    ok = lambda label, passed, detail="": checks.append({"label": label, "passed": bool(passed), "detail": detail})  # noqa: E731
    ok("A resume is selected", app.resume_id, "" if app.resume_id else "Choose which resume to send.")
    ok("Application page link available", app.apply_url, "" if app.apply_url else "No application link saved. Add the employer's page URL.")
    ok("Cover letter drafted (optional)", app.cover_letter, "Generate or write one if the employer asks for it.")
    dup = Application.objects.filter(user=user, fingerprint=app.fingerprint).exclude(pk=app.pk).exclude(status="withdrawn").first()
    ok("Not a duplicate of another application", dup is None, f"You already have '{dup.job_title}' at {dup.company} ({dup.status})." if dup else "")
    if dup:
        warnings.append("Possible duplicate application.")
    if app.job_id and app.resume_id:
        m = matching.ensure_matches(user, app.resume, [app.job]).get(app.job_id)
        if m:
            warnings += m.breakdown.get("eligibility", {}).get("warnings", [])
            ok("Match score is reasonable (40%+)", m.score >= 40, f"Match score is {m.score}%.")
    return {"checks": checks, "warnings": warnings, "ready": all(c["passed"] for c in checks if c["label"] != "Cover letter drafted (optional)")}


def schedule_followup(app: Application, days: int = 7) -> None:
    Reminder.objects.get_or_create(
        user=app.user, application=app, title=f"Follow up: {app.job_title} at {app.company}",
        defaults={"due_at": timezone.now() + timedelta(days=days)},
    )


def process_due_reminders(user) -> int:
    """Create in-app notifications for reminders that came due. Called lazily and by `manage.py send_reminders`."""
    now = timezone.now()
    due = list(Reminder.objects.filter(user=user, done=False, notified_at__isnull=True, due_at__lte=now))
    for r in due:
        Notification.objects.create(
            user=user, kind="reminder", title=r.title, body="This reminder is due.",
            link=f"/applications?open={r.application_id}" if r.application_id else "/reminders",
        )
        r.notified_at = now
        r.save(update_fields=["notified_at"])
    return len(due)
