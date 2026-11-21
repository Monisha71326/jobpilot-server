from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Profile
from apps.core import ai
from apps.core.quota import consume, usage_summary
from apps.jobs import matching
from apps.jobs.models import Job, SavedJob
from apps.resumes.models import Resume

from . import services, writing
from .models import Application, ApplicationActivity, ApplyAttempt, Reminder

MAX_ATTEMPTS = 5
BOARD_ORDER = ["wishlist", "preparing", "applied", "interviewing", "offer", "rejected", "withdrawn"]


def app_dict(a: Application, detail: bool = False) -> dict:
    d = {
        "id": a.id, "job_id": a.job_id, "job_title": a.job_title, "company": a.company, "location": a.location,
        "apply_url": a.apply_url, "status": a.status, "position": a.position, "match_score": a.match_score,
        "resume_id": a.resume_id, "resume_title": a.resume.title if a.resume else None,
        "applied_at": a.applied_at, "applied_via": a.applied_via, "submission_confirmed": a.submission_confirmed_at is not None,
        "review_confirmed_at": a.review_confirmed_at, "has_cover_letter": bool(a.cover_letter),
        "updated_at": a.updated_at, "created_at": a.created_at,
    }
    if detail:
        d["cover_letter"], d["notes"] = a.cover_letter, a.notes
        d["activities"] = [{"id": x.id, "kind": x.kind, "message": x.message, "created_at": x.created_at} for x in a.activities.all()[:60]]
        d["attempts"] = [attempt_dict(x) for x in a.attempts.all()]
        d["reminders"] = [{"id": r.id, "title": r.title, "due_at": r.due_at, "done": r.done} for r in a.reminders.all()]
    return d


def attempt_dict(t: ApplyAttempt) -> dict:
    return {"id": t.id, "attempt_no": t.attempt_no, "state": t.state, "host": t.host, "fields_filled": t.fields_filled,
            "fields_skipped": t.fields_skipped, "error": t.error, "created_at": t.created_at, "updated_at": t.updated_at}


def own_app(request, pk) -> Application:
    return get_object_or_404(Application.objects.select_related("resume", "job"), pk=pk, user=request.user)


def own_resume_or_none(request, rid):
    if not rid:
        return None
    return get_object_or_404(Resume, pk=rid, user=request.user)


def apply_status_change(app: Application, new: str, data: dict) -> Response | None:
    """Central rule: 'applied' needs explicit confirmation that the person really submitted. Returns an error Response or None."""
    if new not in Application.Status.values:
        return Response({"status": ["Unknown status."]}, status=400)
    if new == app.status:
        return None
    now = timezone.now()
    if new == "applied":
        if not data.get("confirm_submitted"):
            return Response({
                "detail": "Only mark an application as Applied after you have actually submitted it on the employer's site.",
                "code": "needs_confirmation",
            }, status=400)
        via = data.get("applied_via") if data.get("applied_via") in Application.Via.values else "manual"
        app.submission_confirmed_at = app.submission_confirmed_at or now
        app.applied_at = app.applied_at or now
        app.applied_via = via
        services.schedule_followup(app)
        services.log(app, "submitted", f"You confirmed this application was submitted ({Application.Via(via).label}).")
        ApplyAttempt.objects.filter(application=app, state__in=["prepared", "autofilled"]).update(state="completed")
    old = app.status
    app.status = new
    app.save()
    services.log(app, "status", f"Moved from {old} to {new}.")
    return None


class ApplicationListView(APIView):
    def get(self, request):
        apps = Application.objects.filter(user=request.user).select_related("resume")
        return Response({"columns": BOARD_ORDER, "results": [app_dict(a) for a in apps]})

    @transaction.atomic
    def post(self, request):
        d, user = request.data, request.user
        job = None
        if d.get("job_id"):
            job = get_object_or_404(Job.objects.visible_to(user), pk=d["job_id"])
            title, company, location, url = job.title, job.company, job.location, job.apply_url
        else:
            title, company = str(d.get("job_title", "")).strip()[:200], str(d.get("company", "")).strip()[:160]
            location, url = str(d.get("location", ""))[:160], str(d.get("apply_url", ""))[:600]
            if not title or not company:
                return Response({"detail": "Job title and company are required."}, status=400)
            if url and not url.lower().startswith(("http://", "https://")):
                return Response({"apply_url": ["Must start with http:// or https://"]}, status=400)
        dup = services.find_duplicate(user, job=job, title=title, company=company, location=location)
        if dup and (job is not None and dup.job_id == job.id or not d.get("force")):
            return Response({"detail": f"You already have an application for '{dup.job_title}' at {dup.company}.",
                             "code": "duplicate", "existing_id": dup.id, "can_force": not (job is not None and dup.job_id == job.id)}, status=409)
        resume = own_resume_or_none(request, d.get("resume_id"))
        reason = {"reason": "Selected by you."} if resume else {}
        if not resume:
            resume, reason = services.choose_resume(user, job)
        status_ = d.get("status") if d.get("status") in ("wishlist", "preparing") else "wishlist"
        score = None
        if job and resume:
            m = matching.ensure_matches(user, resume, [job]).get(job.id)
            score = m.score if m else None
        app = Application.objects.create(
            user=user, job=job, resume=resume, job_title=title, company=company, location=location, apply_url=url,
            status=status_, match_score=score, position=Application.objects.filter(user=user, status=status_).count(),
        )
        services.log(app, "created", f"Added to {status_}." + (f" Resume: {resume.title} ({reason.get('reason', '')})" if resume else ""))
        out = app_dict(app, detail=True)
        out["resume_choice"] = reason
        return Response(out, status=201)


class ApplicationDetailView(APIView):
    def get(self, request, pk):
        return Response(app_dict(own_app(request, pk), detail=True))

    @transaction.atomic
    def patch(self, request, pk):
        app, d = own_app(request, pk), request.data
        changed = []
        if "notes" in d:
            app.notes = str(d["notes"])[:5000]
            changed.append("notes")
        if "cover_letter" in d:
            app.cover_letter = str(d["cover_letter"])[:8000]
            changed.append("cover letter")
        if "apply_url" in d:
            url = str(d["apply_url"]).strip()[:600]
            if url and not url.lower().startswith(("http://", "https://")):
                return Response({"apply_url": ["Must start with http:// or https://"]}, status=400)
            app.apply_url = url
            changed.append("apply link")
        if "resume_id" in d:
            app.resume = own_resume_or_none(request, d["resume_id"])
            app.review_confirmed_at = None  # changed inputs must be re-reviewed
            changed.append("resume")
        if app.job_id is None:
            for f, n in (("job_title", 200), ("company", 160), ("location", 160)):
                if f in d and str(d[f]).strip():
                    setattr(app, f, str(d[f]).strip()[:n])
        if "cover_letter" in d:
            app.review_confirmed_at = None
        if "status" in d:
            err = apply_status_change(app, d["status"], d)
            if err:
                return err
        app.save()
        if changed:
            services.log(app, "note", "Updated " + ", ".join(changed) + ".")
        return Response(app_dict(Application.objects.select_related("resume").get(pk=app.pk), detail=True))

    def delete(self, request, pk):
        own_app(request, pk).delete()
        return Response(status=204)


class MoveView(APIView):
    """Kanban drag-and-drop: change status and (optionally) the order of the destination column."""

    @transaction.atomic
    def post(self, request, pk):
        app, d = own_app(request, pk), request.data
        err = apply_status_change(app, d.get("status", app.status), d)
        if err:
            return err
        ids = d.get("ids")
        if isinstance(ids, list):
            valid = set(Application.objects.filter(user=request.user, status=app.status, id__in=[i for i in ids if isinstance(i, int)]).values_list("id", flat=True))
            for pos, i in enumerate(i for i in ids if i in valid):
                Application.objects.filter(pk=i, user=request.user).update(position=pos)
        return Response(app_dict(Application.objects.select_related("resume").get(pk=app.pk)))


class PrepareView(APIView):
    """Step 1 of assisted apply: eligibility checks + the exact data that will be filled. Nothing is sent anywhere."""

    @transaction.atomic
    def post(self, request, pk):
        app = own_app(request, pk)
        if app.status in ("applied", "interviewing", "offer", "rejected", "withdrawn"):
            return Response({"detail": f"This application is already '{app.status}'."}, status=409)
        if app.status == "wishlist":
            app.status = "preparing"
            app.save()
            services.log(app, "status", "Moved to preparing.")
        report = services.eligibility(request.user, app)
        attempt = app.attempts.filter(state__in=["prepared", "autofilled"]).first()
        if not attempt:
            n = (app.attempts.order_by("-attempt_no").values_list("attempt_no", flat=True).first() or 0) + 1
            attempt = ApplyAttempt.objects.create(application=app, attempt_no=n)
            services.log(app, "prepared", f"Prepared assisted apply (attempt {n}).")
        return Response({
            "application": app_dict(app), "eligibility": report, "attempt": attempt_dict(attempt),
            "form_data": autofill_fields(request.user, app),
            "steps": [
                "Review the checklist and the data below, then press 'I reviewed this'.",
                "Open the employer's application page and click the JobPilot extension's Fill button.",
                "Check every field on the employer's page. Attach your resume file yourself.",
                "Submit on the employer's site. Then come back and press 'I submitted it'.",
            ],
        })


class ReviewView(APIView):
    def post(self, request, pk):
        app = own_app(request, pk)
        report = services.eligibility(request.user, app)
        if report["warnings"] and not request.data.get("acknowledge_warnings"):
            return Response({"detail": "Please acknowledge the warnings to continue.", "code": "warnings", "warnings": report["warnings"]}, status=400)
        if not app.resume_id:
            return Response({"detail": "Select a resume first."}, status=400)
        app.review_confirmed_at = timezone.now()
        app.save(update_fields=["review_confirmed_at", "updated_at"])
        services.log(app, "review", "You reviewed the data to be autofilled." + (" Warnings acknowledged." if report["warnings"] else ""))
        return Response(app_dict(app))


class ConfirmSubmittedView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        app = own_app(request, pk)
        if app.status == "applied":
            return Response(app_dict(app))
        err = apply_status_change(app, "applied", {"confirm_submitted": bool(request.data.get("confirm_submitted")), "applied_via": request.data.get("applied_via", "assisted")})
        return err or Response(app_dict(app))


class AttemptActionView(APIView):
    @transaction.atomic
    def post(self, request, pk, attempt_id, action):
        app = own_app(request, pk)
        t = get_object_or_404(ApplyAttempt, pk=attempt_id, application=app)
        if action == "cancel":
            if t.state in ("completed", "cancelled"):
                return Response({"detail": f"Attempt is already {t.state}."}, status=409)
            t.state = "cancelled"
            t.save()
            services.log(app, "cancelled", f"You cancelled assisted-apply attempt {t.attempt_no}.")
            return Response(attempt_dict(t))
        if action == "retry":
            if app.attempts.filter(state__in=["prepared", "autofilled"]).exists():
                return Response({"detail": "Cancel the active attempt before starting a new one."}, status=409)
            if t.attempt_no >= MAX_ATTEMPTS or app.attempts.count() >= MAX_ATTEMPTS:
                return Response({"detail": f"Maximum of {MAX_ATTEMPTS} attempts reached. Apply manually on the employer's site."}, status=409)
            if app.status == "applied":
                return Response({"detail": "This application is already marked as applied."}, status=409)
            n = app.attempts.order_by("-attempt_no").first().attempt_no + 1
            new = ApplyAttempt.objects.create(application=app, attempt_no=n)
            app.review_confirmed_at = None
            app.save(update_fields=["review_confirmed_at", "updated_at"])
            services.log(app, "retry", f"Started attempt {n}. Please review again.")
            return Response(attempt_dict(new), status=201)
        return Response({"detail": "Unknown action."}, status=404)


def split_name(user) -> tuple[str, str]:
    first, last = user.first_name.strip(), user.last_name.strip()
    if not first and not last:
        parts = user.email.split("@")[0].replace(".", " ").replace("_", " ").title().split()
        first, last = (parts[0], " ".join(parts[1:])) if parts else ("", "")
    return first, last


def autofill_fields(user, app: Application | None = None) -> dict:
    p, (first, last) = user.profile, split_name(user)
    links = p.links or {}
    out = {
        "first_name": first, "last_name": last, "full_name": f"{first} {last}".strip(), "email": user.email, "phone": p.phone,
        "location": p.location, "city": (p.location or "").split(",")[0].strip(), "headline": p.headline,
        "summary": p.summary, "linkedin": links.get("linkedin", ""), "github": links.get("github", ""),
        "portfolio": links.get("portfolio") or links.get("website", ""),
        "years_experience": str(p.years_experience).rstrip("0").rstrip(".") if p.years_experience else "",
        "notice_period_days": str(p.notice_period_days) if p.notice_period_days is not None else "",
    }
    if app:
        out["cover_letter"] = app.cover_letter
    return {k: v for k, v in out.items() if v}


# ---------------------------------------------------------------- browser extension API (scoped key, read-mostly)
class AutofillKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        key = request.headers.get("X-Autofill-Key", "")
        if not key:
            raise AuthenticationFailed("Missing autofill key.")
        profile = Profile.objects.select_related("user").filter(autofill_key=key, user__is_active=True).first()
        if not profile:
            raise AuthenticationFailed("Invalid autofill key.")
        return profile.user, None

    def authenticate_header(self, request):
        return "AutofillKey"


class AutofillProfileView(APIView):
    authentication_classes = [AutofillKeyAuthentication]
    throttle_scope = "auth"

    def get(self, request):
        app = (
            Application.objects.filter(user=request.user, review_confirmed_at__isnull=False, attempts__state="prepared")
            .select_related("resume").distinct().order_by("-updated_at").first()
        )
        attempt = app.attempts.filter(state="prepared").first() if app else None
        return Response({
            "fields": autofill_fields(request.user, app if attempt else None),
            "attempt": ({"id": attempt.id, "attempt_no": attempt.attempt_no, "application_id": app.id,
                         "job_title": app.job_title, "company": app.company, "apply_url": app.apply_url} if attempt else None),
            "note": "The extension fills fields only. It never submits forms, solves CAPTCHAs, or uploads files.",
        })


class AutofillReportView(APIView):
    authentication_classes = [AutofillKeyAuthentication]
    throttle_scope = "auth"

    def post(self, request):
        t = ApplyAttempt.objects.select_related("application").filter(pk=request.data.get("attempt_id"), application__user=request.user).first()
        if not t:
            return Response({"detail": "Attempt not found."}, status=404)
        if t.state in ("cancelled", "completed"):
            return Response({"detail": f"Attempt is {t.state}."}, status=409)
        filled = [str(x)[:60] for x in (request.data.get("filled") or [])][:40] if isinstance(request.data.get("filled"), list) else []
        skipped = [str(x)[:60] for x in (request.data.get("skipped") or [])][:40] if isinstance(request.data.get("skipped"), list) else []
        error = str(request.data.get("error") or "")[:300]
        t.host = str(request.data.get("host") or "")[:120]
        t.fields_filled, t.fields_skipped, t.error = filled, skipped, error
        t.state = "failed" if error and not filled else "autofilled"
        t.save()
        if t.state == "failed":
            services.log(t.application, "error", f"Autofill failed on {t.host or 'the page'}: {error}")
        else:
            services.log(t.application, "autofill", f"Autofilled {len(filled)} field(s) on {t.host or 'the page'}. Review before you submit.", filled=filled, skipped=skipped)
        return Response({"state": t.state})


# ---------------------------------------------------------------- reminders
def _parse_due(value):
    dt = parse_datetime(str(value or ""))
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


class ReminderListView(APIView):
    def get(self, request):
        services.process_due_reminders(request.user)
        qs = Reminder.objects.filter(user=request.user).select_related("application")
        if request.query_params.get("scope") == "open":
            qs = qs.filter(done=False)
        return Response([{
            "id": r.id, "title": r.title, "due_at": r.due_at, "done": r.done, "application_id": r.application_id,
            "overdue": (not r.done) and r.due_at < timezone.now(),
        } for r in qs[:200]])

    def post(self, request):
        due, title = _parse_due(request.data.get("due_at")), str(request.data.get("title", "")).strip()[:160]
        if not title or not due:
            return Response({"detail": "A title and a valid due date/time are required."}, status=400)
        app = job = None
        if request.data.get("application_id"):
            app = get_object_or_404(Application, pk=request.data["application_id"], user=request.user)
        if request.data.get("job_id"):
            job = get_object_or_404(Job.objects.visible_to(request.user), pk=request.data["job_id"])
        r = Reminder.objects.create(user=request.user, title=title, due_at=due, application=app, job=job)
        return Response({"id": r.id, "title": r.title, "due_at": r.due_at, "done": r.done}, status=201)


class ReminderDetailView(APIView):
    def patch(self, request, pk):
        r = get_object_or_404(Reminder, pk=pk, user=request.user)
        if "done" in request.data:
            r.done = bool(request.data["done"])
        if request.data.get("title"):
            r.title = str(request.data["title"])[:160]
        if request.data.get("due_at"):
            due = _parse_due(request.data["due_at"])
            if not due:
                return Response({"due_at": ["Invalid date/time."]}, status=400)
            r.due_at, r.notified_at = due, None
        r.save()
        return Response({"id": r.id, "title": r.title, "due_at": r.due_at, "done": r.done})

    def delete(self, request, pk):
        get_object_or_404(Reminder, pk=pk, user=request.user).delete()
        return Response(status=204)


# ---------------------------------------------------------------- writing
class GenerateTextView(APIView):
    throttle_scope = "ai"

    def post(self, request):
        d = request.data
        app = get_object_or_404(Application.objects.select_related("job", "resume"), pk=d["application_id"], user=request.user) if d.get("application_id") else None
        job = app.job if app else (get_object_or_404(Job.objects.visible_to(request.user), pk=d["job_id"]) if d.get("job_id") else None)
        resume = own_resume_or_none(request, d.get("resume_id")) or (app.resume if app else None)
        if not resume:
            resume = Resume.objects.filter(user=request.user, is_primary=True).first() or Resume.objects.filter(user=request.user).first()
        if not job and not app:
            return Response({"detail": "Choose a job or application first."}, status=400)
        consume(request.user, "ai_cover_letter")
        match = matching.ensure_matches(request.user, resume, [job]).get(job.id) if job and resume else None
        if job is None and app:  # manual application without a Job row
            job = Job(title=app.job_title, company=app.company, description="")
        res = writing.generate(request.user, resume, job, match.breakdown if match else None, d.get("kind", "cover_letter"), d.get("tone", "professional"), str(d.get("extra", "")))
        saved = False
        if app and d.get("save") and d.get("kind", "cover_letter") == "cover_letter":
            app.cover_letter, app.review_confirmed_at = res.text, None
            app.save(update_fields=["cover_letter", "review_confirmed_at", "updated_at"])
            services.log(app, "note", f"Cover letter {'generated by local AI' if res.engine == 'ollama' else 'drafted from a template'} and saved.")
            saved = True
        return Response({**res.as_dict(), "saved_to_application": saved})


# ---------------------------------------------------------------- dashboard
class DashboardView(APIView):
    def get(self, request):
        user = request.user
        services.process_due_reminders(user)
        apps = list(Application.objects.filter(user=user))
        counts = Counter(a.status for a in apps)
        now = timezone.now()
        weeks = []
        for i in range(7, -1, -1):
            start = (now - timedelta(weeks=i + 1))
            end = now - timedelta(weeks=i)
            weeks.append({"label": end.strftime("%d %b"), "applied": sum(1 for a in apps if a.applied_at and start < a.applied_at <= end)})
        reminders = Reminder.objects.filter(user=user, done=False).order_by("due_at")[:5]
        activity = ApplicationActivity.objects.filter(application__user=user).select_related("application").order_by("-created_at")[:8]
        primary = Resume.objects.filter(user=user, is_primary=True).first()
        applied_total = sum(counts.get(s, 0) for s in ("applied", "interviewing", "offer", "rejected"))
        responses = sum(counts.get(s, 0) for s in ("interviewing", "offer", "rejected"))
        from apps.core.models import Notification

        return Response({
            "counts": {s: counts.get(s, 0) for s in BOARD_ORDER},
            "total_applications": len(apps),
            "response_rate": round(100 * responses / applied_total) if applied_total else None,
            "saved_jobs": SavedJob.objects.filter(user=user).count(),
            "weekly": weeks,
            "reminders": [{"id": r.id, "title": r.title, "due_at": r.due_at, "overdue": r.due_at < now, "application_id": r.application_id} for r in reminders],
            "recent_activity": [{"id": a.id, "kind": a.kind, "message": a.message, "created_at": a.created_at,
                                 "application_id": a.application_id, "label": f"{a.application.job_title} - {a.application.company}"} for a in activity],
            "resume": ({"id": primary.id, "title": primary.title, "score": primary.analysis.get("score") if primary.analysis else None} if primary else None),
            "profile_completeness": profile_completeness(user),
            "unread_notifications": Notification.objects.filter(user=user, is_read=False).count(),
            "usage": usage_summary(user),
            "ai": {k: ai.status().get(k) for k in ("enabled", "ready", "model", "reachable", "model_installed")},
        })


def profile_completeness(user) -> dict:
    p = user.profile
    items = [
        ("Name", bool(user.first_name)), ("Headline", bool(p.headline)), ("Phone", bool(p.phone)), ("Location", bool(p.location)),
        ("Skills", len(p.skills) >= 3), ("Target roles", bool(p.desired_roles)), ("Resume uploaded", user.resumes.exists()),
        ("Links (LinkedIn/GitHub)", bool(p.links)),
    ]
    done = sum(1 for _, ok in items if ok)
    return {"percent": round(100 * done / len(items)), "missing": [n for n, ok in items if not ok]}
