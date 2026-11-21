"""Free usage quotas. Local AI costs nothing, but quotas protect a shared/self-hosted machine from abuse."""
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import APIException

from .models import Plan, UsageRecord

DEFAULT_DAILY_LIMITS = {
    "ai_chat": 150,
    "ai_cover_letter": 40,
    "ai_resume": 40,
    "ai_interview": 120,
    "ai_roadmap": 30,
    "job_refresh": 20,
    "job_import": 60,
    "resume_upload": 25,
}


class QuotaExceeded(APIException):
    status_code = 429
    default_detail = "Daily free quota reached for this feature. It resets at midnight."
    default_code = "quota_exceeded"


def get_plan(user) -> Plan | None:
    # Billing is disabled: everyone is on the default free plan.
    if settings.BILLING_ENABLED and hasattr(user, "profile") and user.profile.plan_id:
        return user.profile.plan
    return Plan.objects.filter(is_default=True, is_active=True).first()


def limit_for(user, feature: str) -> int:
    plan = get_plan(user)
    if plan and feature in plan.daily_limits:
        return int(plan.daily_limits[feature])
    return DEFAULT_DAILY_LIMITS.get(feature, 100)


def consume(user, feature: str, amount: int = 1) -> int:
    """Atomically record usage; raise QuotaExceeded when the daily limit would be exceeded. Returns remaining."""
    limit = limit_for(user, feature)
    today = timezone.localdate()
    with transaction.atomic():
        rec, _ = UsageRecord.objects.select_for_update().get_or_create(user=user, feature=feature, day=today)
        if rec.count + amount > limit:
            raise QuotaExceeded()
        UsageRecord.objects.filter(pk=rec.pk).update(count=F("count") + amount)
    return limit - rec.count - amount


def usage_summary(user) -> dict:
    today = timezone.localdate()
    used = dict(UsageRecord.objects.filter(user=user, day=today).values_list("feature", "count"))
    return {
        f: {"used": used.get(f, 0), "limit": limit_for(user, f)}
        for f in sorted(set(DEFAULT_DAILY_LIMITS) | set(used))
    }
