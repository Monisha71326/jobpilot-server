from django.conf import settings
from django.db import models


class Plan(models.Model):
    """Subscription architecture. BILLING_ENABLED stays False, so every user is on the default free plan.

    daily_limits maps a feature key to the max uses per day; a missing key falls back to DEFAULT_DAILY_LIMITS.
    """

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=60)
    daily_limits = models.JSONField(default=dict, blank=True)
    monthly_price_inr = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class UsageRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="usage_records")
    feature = models.CharField(max_length=40)
    day = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "feature", "day"], name="uniq_usage_user_feature_day")]
        indexes = [models.Index(fields=["day", "feature"])]

    def __str__(self):
        return f"{self.user_id}:{self.feature}:{self.day}={self.count}"


class Notification(models.Model):
    class Kind(models.TextChoices):
        REMINDER = "reminder", "Reminder"
        APPLICATION = "application", "Application"
        SYSTEM = "system", "System"
        JOB = "job", "Job"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]
