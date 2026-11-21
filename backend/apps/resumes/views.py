import re

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import ai
from apps.core.quota import consume

from . import analyzer, builder, parser
from .models import Resume, ResumeVersion
from .serializers import ResumeDetailSerializer, ResumeSerializer, ResumeVersionSerializer


def own_resume(request, pk) -> Resume:
    # Authorization: always scoped to the requesting user; others' ids return 404 (no existence leak).
    return get_object_or_404(Resume.objects.prefetch_related("versions"), pk=pk, user=request.user)


def next_version_no(resume) -> int:
    return (resume.versions.aggregate(m=Max("version_no"))["m"] or 0) + 1


@transaction.atomic
def add_version(resume, content, template, note="") -> ResumeVersion:
    for _ in range(3):  # retry on rare concurrent version-number collisions
        try:
            with transaction.atomic():
                return ResumeVersion.objects.create(
                    resume=resume, version_no=next_version_no(resume), template=template, content=content, note=note[:160]
                )
        except IntegrityError:
            continue
    raise RuntimeError("Could not allocate a version number")


class ResumeListView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        qs = Resume.objects.filter(user=request.user).prefetch_related("versions")
        return Response(ResumeSerializer(qs, many=True).data)

    def post(self, request):
        """Upload and parse a PDF/DOCX resume."""
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "Attach a PDF or DOCX file in the 'file' field."}, status=400)
        consume(request.user, "resume_upload")
        try:
            ftype = parser.validate_upload(upload)
            data = upload.read()
            upload.seek(0)
            text, pages, extra = parser.extract_text(data, ftype)
        except parser.ResumeError as e:
            return Response({"detail": str(e)}, status=400)
        if len(text) < 80:
            return Response(
                {"detail": "Very little text could be read. Scanned/image-only resumes are not supported; export a text-based PDF or DOCX."},
                status=400,
            )
        parsed = parser.parse_resume_text(text)
        parsed["tables"] = extra.get("tables", 0)
        title = (request.data.get("title") or upload.name.rsplit(".", 1)[0])[:120]
        first = not Resume.objects.filter(user=request.user).exists()
        resume = Resume.objects.create(
            user=request.user, title=title, source="upload", file=upload, original_filename=upload.name[:255],
            file_type=ftype, page_count=pages, parsed_text=text, parsed_data=parsed, skills=parsed["skills"], is_primary=first,
        )
        return Response(ResumeDetailSerializer(resume).data, status=status.HTTP_201_CREATED)


class ResumeBuilderCreateView(APIView):
    def post(self, request):
        template = request.data.get("template", "classic")
        if template not in builder.TEMPLATES:
            template = "classic"
        resume = Resume.objects.create(
            user=request.user, title=str(request.data.get("title") or "My resume")[:120], source="builder",
            is_primary=not Resume.objects.filter(user=request.user).exists(),
        )
        add_version(resume, builder.blank_content(request.user), template, "Created from your profile")
        resume = own_resume(request, resume.pk)
        return Response(ResumeDetailSerializer(resume).data, status=201)


class TemplatesView(APIView):
    def get(self, request):
        return Response([{"id": k, **v} for k, v in builder.TEMPLATES.items()])


class ResumeDetailView(APIView):
    def get(self, request, pk):
        return Response(ResumeDetailSerializer(own_resume(request, pk)).data)

    def patch(self, request, pk):
        r = own_resume(request, pk)
        title = str(request.data.get("title", "")).strip()[:120]
        if not title:
            return Response({"title": ["Title is required."]}, status=400)
        r.title = title
        r.save(update_fields=["title", "updated_at"])
        return Response(ResumeDetailSerializer(r).data)

    def delete(self, request, pk):
        r = own_resume(request, pk)
        was_primary = r.is_primary
        # Applications keep history: the FK uses SET_NULL, so deleting a resume never deletes application records.
        if r.file:
            r.file.delete(save=False)
        r.delete()
        if was_primary:
            nxt = Resume.objects.filter(user=request.user).first()
            if nxt:
                nxt.is_primary = True
                nxt.save(update_fields=["is_primary"])
        return Response(status=204)


class ResumeFileView(APIView):
    def get(self, request, pk):
        r = own_resume(request, pk)
        if not r.file:
            return Response({"detail": "This resume has no uploaded file."}, status=404)
        return FileResponse(r.file.open("rb"), as_attachment=True, filename=r.original_filename or f"resume.{r.file_type}")


class SetPrimaryView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        r = own_resume(request, pk)
        Resume.objects.filter(user=request.user, is_primary=True).exclude(pk=r.pk).update(is_primary=False)
        r.is_primary = True
        r.save(update_fields=["is_primary"])
        return Response(ResumeSerializer(r).data)


class AnalyzeView(APIView):
    throttle_scope = "ai"

    def post(self, request, pk):
        r = own_resume(request, pk)
        consume(request.user, "ai_resume")
        text = r.search_text()
        if len(text) < 50:
            return Response({"detail": "This resume has no content to analyze yet."}, status=400)
        parsed = parser.parse_resume_text(text)
        job_text, job = "", None
        job_id = request.data.get("job_id")
        if job_id:
            from apps.jobs.models import Job

            job = Job.objects.visible_to(request.user).filter(pk=job_id).first()
            if not job:
                return Response({"detail": "Job not found."}, status=404)
            job_text = f"{job.title}\n{job.description}"
        result = analyzer.analyze(
            text, parsed, page_count=r.page_count, tables=r.parsed_data.get("tables", 0) if r.parsed_data else 0, job_text=job_text
        )
        fallback = "Top improvements:\n" + "\n".join(f"- {i['fix']}" for i in result["improvements"][:5]) if result["improvements"] else "Your resume passes all automated checks. Tailor it to each job's keywords."
        target = f"Target job: {job.title} at {job.company}\n{ai.wrap_untrusted('job', job.description, 3000)}\n" if job else ""
        prompt = (
            "Review this resume and give 5 specific, actionable improvements. For weak bullets, show a rewritten version. "
            "Do not invent employers, degrees or numbers - use placeholders like [X%] when a metric is needed.\n"
            f"{target}{ai.wrap_untrusted('resume', text)}"
        )
        res = ai.ask(
            [{"role": "user", "content": prompt}],
            system="You are a precise, honest resume coach. " + ai.UNTRUSTED_NOTE, fallback=fallback, max_tokens=700,
        )
        if not job:
            r.analysis = result
            r.analysis_at = timezone.now()
            r.save(update_fields=["analysis", "analysis_at"])
        return Response({"analysis": result, "ai": res.as_dict()})


class ToBuilderView(APIView):
    """Create an editable builder version from a parsed upload (review it afterwards - parsing is best-effort)."""

    def post(self, request, pk):
        r = own_resume(request, pk)
        if not r.parsed_data:
            return Response({"detail": "Nothing parsed to convert."}, status=400)
        v = add_version(r, builder.from_parsed(r.parsed_data, request.user), "classic", "Imported from uploaded file")
        return Response(ResumeVersionSerializer(v).data, status=201)


class VersionsView(APIView):
    def get(self, request, pk):
        r = own_resume(request, pk)
        return Response(ResumeVersionSerializer(sorted(r.versions.all(), key=lambda v: -v.version_no), many=True).data)

    def post(self, request, pk):
        r = own_resume(request, pk)
        template = request.data.get("template", "classic")
        if template not in builder.TEMPLATES:
            return Response({"template": ["Unknown template."]}, status=400)
        try:
            content = builder.normalize_content(request.data.get("content"))
        except ValueError as e:
            return Response({"content": [str(e)]}, status=400)
        v = add_version(r, content, template, str(request.data.get("note", "")))
        Resume.objects.filter(pk=r.pk).update(updated_at=timezone.now())
        return Response(ResumeVersionSerializer(v).data, status=201)


class ExportView(APIView):
    def get(self, request, pk):
        r = own_resume(request, pk)
        versions = sorted(r.versions.all(), key=lambda v: -v.version_no)
        if not versions:
            return Response({"detail": "No builder content to export."}, status=404)
        wanted = request.query_params.get("version")
        v = next((x for x in versions if str(x.version_no) == wanted), None) if wanted else versions[0]
        if not v:
            return Response({"detail": "Version not found."}, status=404)
        data = builder.export_docx(v.content, request.query_params.get("template") or v.template)
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", r.title)[:60] or "resume"
        resp = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        resp["Content-Disposition"] = f'attachment; filename="{name}_v{v.version_no}.docx"'
        return resp


class ApplyToProfileView(APIView):
    """Explicit, user-triggered copy of parsed skills/experience into the profile."""

    def post(self, request, pk):
        r = own_resume(request, pk)
        p = request.user.profile
        merged = list(dict.fromkeys([*p.skills, *r.skills]))[:60]
        p.skills = merged
        yrs = (r.parsed_data or {}).get("years_experience")
        if yrs and not p.years_experience:
            p.years_experience = yrs
        p.save()
        return Response({"skills": p.skills, "years_experience": float(p.years_experience)})
