import re
from datetime import timedelta

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.quota import consume
from apps.resumes.models import Resume

from . import ingest, matching
from .adapters import ADAPTERS
from .adapters import user_provided
from .adapters.base import FetchError
from .models import Job, JobMatch, JobSource, SavedJob, TrackedBoard

PAGE_SIZE = 20
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{2,60}$")


def pick_resume(request) -> Resume | None:
    rid = request.query_params.get("resume_id") or request.data.get("resume_id") if hasattr(request, "data") else None
    qs = Resume.objects.filter(user=request.user)
    if rid:
        return qs.filter(pk=rid).first()
    return qs.filter(is_primary=True).first() or qs.first()


def job_dict(job: Job, match: JobMatch | None = None, saved: bool = False, app_status: str | None = None, detail: bool = False) -> dict:
    d = {
        "id": job.id, "title": job.title, "company": job.company, "location": job.location, "is_remote": job.is_remote,
        "employment_type": job.employment_type, "skills": job.skills, "min_experience": job.min_experience,
        "max_experience": job.max_experience, "salary_text": job.salary_text, "apply_url": job.apply_url,
        "posted_at": job.posted_at, "last_checked_at": job.last_checked_at, "is_active": job.is_active,
        "imported_by_me": job.added_by_id is not None,
        "source": {"slug": job.source.slug, "name": job.source.name, "kind": job.source.kind,
                   "attribution": job.source.attribution, "terms_url": job.source.terms_url},
        "match_score": match.score if match else None,
        "match_verdict": match.breakdown.get("verdict") if match else None,
        "is_saved": saved, "application_status": app_status,
        "snippet": (job.description or "")[:260],
    }
    if detail:
        d["description"] = job.description
    return d


def user_context(user, job_ids):
    from apps.applications.models import Application

    saved = set(SavedJob.objects.filter(user=user, job_id__in=job_ids).values_list("job_id", flat=True))
    apps = dict(Application.objects.filter(user=user, job_id__in=job_ids).values_list("job_id", "status"))
    return saved, apps


class JobListView(APIView):
    def get(self, request):
        q = request.query_params
        user = request.user
        qs = Job.objects.visible_to(user).filter(is_active=True).select_related("source")
        for term in (q.get("q") or "").split()[:6]:
            qs = qs.filter(Q(title__icontains=term) | Q(company__icontains=term) | Q(description__icontains=term))
        for s in [x.strip() for x in (q.get("skills") or "").split(",") if x.strip()][:10]:
            qs = qs.filter(skills_text__icontains=f"|{s.lower()}|")
        if q.get("location"):
            qs = qs.filter(location__icontains=q["location"][:80])
        if q.get("remote") in ("true", "1"):
            qs = qs.filter(is_remote=True)
        elif q.get("remote") in ("false", "0"):
            qs = qs.filter(is_remote=False)
        if q.get("experience", "").isdigit():
            qs = qs.filter(Q(min_experience__isnull=True) | Q(min_experience__lte=int(q["experience"])))
        if q.get("source"):
            qs = qs.filter(source__slug=q["source"])
        if q.get("posted_within", "").isdigit():
            qs = qs.filter(posted_at__gte=timezone.now() - timedelta(days=int(q["posted_within"])))
        if q.get("saved") in ("true", "1"):
            qs = qs.filter(saved_by__user=user)
        qs = qs.order_by("-posted_at", "-first_seen_at", "-id")

        resume = pick_resume(request)
        page_no = int(q["page"]) if q.get("page", "").isdigit() else 1
        if q.get("sort") == "match" and resume:
            jobs = list(qs[:300])
            matches = matching.ensure_matches(user, resume, jobs)
            jobs.sort(key=lambda j: -(matches[j.id].score if j.id in matches else -1))
            paginator = Paginator(jobs, PAGE_SIZE)
        else:
            paginator = Paginator(qs, PAGE_SIZE)
        try:
            page = paginator.page(page_no)
        except EmptyPage:
            page = paginator.page(paginator.num_pages) if paginator.num_pages else None
        items = list(page.object_list) if page else []
        matches = matching.ensure_matches(user, resume, items) if resume else {}
        saved, apps = user_context(user, [j.id for j in items])
        return Response({
            "count": paginator.count, "page": page.number if page else 1, "pages": paginator.num_pages,
            "has_resume": resume is not None,
            "results": [job_dict(j, matches.get(j.id), j.id in saved, apps.get(j.id)) for j in items],
        })


class JobDetailView(APIView):
    def get(self, request, pk):
        job = get_object_or_404(Job.objects.visible_to(request.user).select_related("source"), pk=pk)
        resume = pick_resume(request)
        match = matching.ensure_matches(request.user, resume, [job]).get(job.id) if resume else None
        saved, apps = user_context(request.user, [job.id])
        from apps.applications.models import Application

        dup = (
            Application.objects.filter(user=request.user, job__fingerprint=job.fingerprint).exclude(job=job).values("id", "job__title", "job__company", "status").first()
        )
        d = job_dict(job, match, job.id in saved, apps.get(job.id), detail=True)
        d["match"] = match.breakdown if match else None
        d["possible_duplicate_application"] = dup
        return Response(d)

    def delete(self, request, pk):
        job = get_object_or_404(Job, pk=pk, added_by=request.user)  # only your own imports can be deleted
        job.delete()
        return Response(status=204)


class JobImportView(APIView):
    def post(self, request):
        d = request.data
        url, text = str(d.get("url") or "").strip(), str(d.get("text") or "").strip()
        if not url and not text:
            return Response({"detail": "Provide a job link or paste the job description."}, status=400)
        consume(request.user, "job_import")
        try:
            n = user_provided.from_url(url) if url and not text else user_provided.from_text(
                text, str(d.get("title") or ""), str(d.get("company") or ""), str(d.get("location") or ""), url)
        except FetchError as e:
            return Response({"detail": str(e), "needs_paste": True}, status=400)
        if d.get("title"):
            n.title = str(d["title"])[:200]
        if d.get("company"):
            n.company = str(d["company"])[:160]
        if not n.title:
            return Response({"detail": "Could not determine the job title. Please enter it.", "needs_paste": True}, status=400)
        n.external_id = ingest.external_id_for(n)
        ingest.ensure_sources()
        source = JobSource.objects.get(slug="user")
        existed = Job.objects.filter(source=source, external_id=n.external_id, added_by=request.user).exists()
        ingest.upsert_jobs(source, [n], added_by=request.user)
        job = Job.objects.select_related("source").get(source=source, external_id=n.external_id, added_by=request.user)
        resume = pick_resume(request)
        m = matching.ensure_matches(request.user, resume, [job]).get(job.id) if resume else None
        out = job_dict(job, m)
        out["duplicate"] = existed
        return Response(out, status=200 if existed else 201)


class SourcesView(APIView):
    def get(self, request):
        ingest.ensure_sources()
        now = timezone.now()
        boards = list(TrackedBoard.objects.filter(user=request.user).select_related("source"))
        out = []
        for s in JobSource.objects.filter(is_active=True).order_by("kind", "name"):
            a = ADAPTERS.get(s.slug)
            nxt = s.last_fetched_at + timedelta(minutes=s.min_refresh_minutes) if s.last_fetched_at else None
            out.append({
                "slug": s.slug, "name": s.name, "kind": s.kind, "attribution": s.attribution, "terms_url": s.terms_url,
                "refreshable": a is not None, "needs_board_token": bool(a and a.needs_board_token),
                "last_fetched_at": s.last_fetched_at, "next_allowed_at": nxt if nxt and nxt > now else None,
                "job_count": s.jobs.filter(is_active=True).filter(Q(added_by__isnull=True) | Q(added_by=request.user)).count(),
                "enabled": settings.JOB_SOURCES_ENABLED,
            })
        return Response({"sources": out, "boards": [
            {"id": b.id, "source": b.source.slug, "token": b.token, "last_fetched_at": b.last_fetched_at, "last_error": b.last_error} for b in boards
        ]})


class RefreshSourceView(APIView):
    def post(self, request, slug):
        adapter = ADAPTERS.get(slug)
        if not adapter:
            return Response({"detail": "This source cannot be refreshed."}, status=404)
        if not settings.JOB_SOURCES_ENABLED:
            return Response({"detail": "Fetching from external job sources is disabled (JOB_SOURCES_ENABLED=false)."}, status=503)
        ingest.ensure_sources()
        source = JobSource.objects.get(slug=slug)
        token = str(request.data.get("token") or "").strip()
        board = None
        if adapter.needs_board_token:
            if not TOKEN_RE.match(token):
                return Response({"detail": "Enter the company's board name (letters, numbers, dashes)."}, status=400)
            board, _ = TrackedBoard.objects.get_or_create(user=request.user, source=source, token=token)
            last = board.last_fetched_at
        else:
            last = source.last_fetched_at
        now = timezone.now()
        if last and now - last < timedelta(minutes=adapter.min_refresh_minutes):
            return Response({
                "skipped": True, "next_allowed_at": last + timedelta(minutes=adapter.min_refresh_minutes),
                "message": f"{adapter.name} was checked recently. To respect its usage rules, it can be refreshed every {adapter.min_refresh_minutes} minutes.",
            })
        consume(request.user, "job_refresh")
        query = str(request.data.get("query") or "").strip()[:80]
        try:
            items = adapter.fetch(query=query, token=token)
        except FetchError as e:
            if board:
                board.last_error = str(e)[:200]
                board.save(update_fields=["last_error"])
            return Response({"detail": str(e)}, status=502)
        stats = ingest.upsert_jobs(source, items, deactivate_missing_prefix=f"{token}:" if adapter.full_listing else "")
        source.last_fetched_at = now
        source.save(update_fields=["last_fetched_at"])
        if board:
            board.last_fetched_at, board.last_error = now, ""
            board.save(update_fields=["last_fetched_at", "last_error"])
        return Response({"skipped": False, "fetched": len(items), **stats, "attribution": adapter.attribution})


class LoadDemoView(APIView):
    """One-click fictional sample jobs (clearly labelled DEMO) so a fresh install is explorable offline."""

    def post(self, request):
        return Response(ingest.load_demo_jobs())


class TrackedBoardDeleteView(APIView):
    def delete(self, request, pk):
        get_object_or_404(TrackedBoard, pk=pk, user=request.user).delete()
        return Response(status=204)


class SavedJobsView(APIView):
    def get(self, request):
        rows = SavedJob.objects.filter(user=request.user).select_related("job__source")
        resume = pick_resume(request)
        jobs = [r.job for r in rows if r.job.added_by_id in (None, request.user.id)]
        matches = matching.ensure_matches(request.user, resume, jobs) if resume else {}
        saved, apps = user_context(request.user, [j.id for j in jobs])
        notes = {r.job_id: r.note for r in rows}
        return Response([{**job_dict(j, matches.get(j.id), True, apps.get(j.id)), "note": notes.get(j.id, "")} for j in jobs])

    def post(self, request):
        job = get_object_or_404(Job.objects.visible_to(request.user), pk=request.data.get("job_id"))
        obj, created = SavedJob.objects.get_or_create(user=request.user, job=job, defaults={"note": str(request.data.get("note", ""))[:300]})
        return Response({"saved": True, "created": created}, status=201 if created else 200)


class SavedJobDetailView(APIView):
    def delete(self, request, job_id):
        SavedJob.objects.filter(user=request.user, job_id=job_id).delete()
        return Response(status=204)

    def patch(self, request, job_id):
        obj = get_object_or_404(SavedJob, user=request.user, job_id=job_id)
        obj.note = str(request.data.get("note", ""))[:300]
        obj.save(update_fields=["note"])
        return Response({"note": obj.note})


class RecommendedView(APIView):
    def get(self, request):
        resume = pick_resume(request)
        if not resume:
            return Response({"has_resume": False, "results": []})
        jobs = list(Job.objects.visible_to(request.user).filter(is_active=True).select_related("source").order_by("-posted_at", "-id")[:200])
        matches = matching.ensure_matches(request.user, resume, jobs)
        jobs.sort(key=lambda j: -matches[j.id].score)
        top = jobs[:6]
        saved, apps = user_context(request.user, [j.id for j in top])
        return Response({"has_resume": True, "results": [job_dict(j, matches[j.id], j.id in saved, apps.get(j.id)) for j in top]})
