from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UsageRecord


def health(request):
    return JsonResponse({"status": "ok"})


class AdminStatsView(APIView):
    """Platform-wide numbers for staff only. No private user content (resumes, letters, chats) is exposed here."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.applications.models import Application
        from apps.assistant.models import AIConversation, InterviewSession
        from apps.jobs.models import Job, JobSource
        from apps.resumes.models import Resume

        User = get_user_model()
        week = timezone.now() - timedelta(days=7)
        today = timezone.localdate()
        return Response({
            "users": {"total": User.objects.count(), "new_7d": User.objects.filter(date_joined__gte=week).count()},
            "resumes": Resume.objects.count(),
            "jobs": {
                "total": Job.objects.count(), "active": Job.objects.filter(is_active=True).count(),
                "by_source": list(Job.objects.values("source__name").annotate(n=Count("id")).order_by("-n")),
            },
            "sources": [{"slug": s.slug, "name": s.name, "last_fetched_at": s.last_fetched_at, "is_active": s.is_active} for s in JobSource.objects.all()],
            "applications": {"total": Application.objects.count(), "by_status": list(Application.objects.values("status").annotate(n=Count("id")))},
            "conversations": AIConversation.objects.count(),
            "interviews": InterviewSession.objects.count(),
            "usage_today": list(UsageRecord.objects.filter(day=today).values("feature").annotate(total=Sum("count")).order_by("-total")),
            "admin_url": "/admin/",
        })
