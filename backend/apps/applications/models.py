from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.jobs.models import normalize_fp


class Application(models.Model):
    class Status(models.TextChoices):
        WISHLIST = "wishlist", "Wishlist"
        PREPARING = "preparing", "Preparing"
        APPLIED = "applied", "Applied"
        INTERVIEWING = "interviewing", "Interviewing"
        OFFER = "offer", "Offer"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class Via(models.TextChoices):
        MANUAL = "manual", "On the employer's site (manual)"
        ASSISTED = "assisted", "Autofill-assisted, submitted by me"
        OTHER = "other", "Other (email, referral, ...)"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    job = models.ForeignKey("jobs.Job", null=True, blank=True, on_delete=models.SET_NULL, related_name="applications")
    resume = models.ForeignKey("resumes.Resume", null=True, blank=True, on_delete=models.SET_NULL, related_name="applications")
    # Snapshot so history survives job/resume deletion.
    job_title = models.CharField(max_length=200)
    company = models.CharField(max_length=160)
    location = models.CharField(max_length=160, blank=True)
    apply_url = models.URLField(max_length=600, blank=True)
    fingerprint = models.CharField(max_length=40, db_index=True, blank=True)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.WISHLIST)
    position = models.PositiveIntegerField(default=0)
    match_score = models.PositiveSmallIntegerField(null=True, blank=True)
    cover_letter = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    # "applied" is only ever set after the user explicitly confirms they submitted on the employer's site.
    submission_confirmed_at = models.DateTimeField(null=True, blank=True)
    applied_via = models.CharField(max_length=10, choices=Via.choices, blank=True)
    review_confirmed_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "job"], condition=Q(job__isnull=False), name="uniq_application_user_job"),
            models.CheckConstraint(
                condition=~Q(status="applied") | Q(submission_confirmed_at__isnull=False), name="applied_requires_confirmation"
            ),
        ]
        indexes = [models.Index(fields=["user", "status"]), models.Index(fields=["user", "-updated_at"])]

    def save(self, *args, **kwargs):
        self.fingerprint = normalize_fp(self.job_title, self.company, self.location)
        super().save(*args, **kwargs)


class ApplicationActivity(models.Model):
    class Kind(models.TextChoices):
        CREATED = "created", "Created"
        STATUS = "status", "Status change"
        NOTE = "note", "Note"
        REVIEW = "review", "Reviewed"
        PREPARED = "prepared", "Prepared for assisted apply"
        AUTOFILL = "autofill", "Autofill report"
        ERROR = "error", "Error"
        CANCELLED = "cancelled", "Cancelled"
        RETRY = "retry", "Retry"
        SUBMITTED = "submitted", "Submission confirmed by you"

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="activities")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    message = models.CharField(max_length=400)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["application", "-created_at"])]


class Reminder(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminders")
    application = models.ForeignKey(Application, null=True, blank=True, on_delete=models.CASCADE, related_name="reminders")
    job = models.ForeignKey("jobs.Job", null=True, blank=True, on_delete=models.CASCADE, related_name="reminders")
    title = models.CharField(max_length=160)
    due_at = models.DateTimeField()
    done = models.BooleanField(default=False)
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["done", "due_at"]
        indexes = [models.Index(fields=["user", "done", "due_at"])]


class ApplyAttempt(models.Model):
    """One run of the assisted-apply workflow. The extension fills fields; the person reviews and submits."""

    class State(models.TextChoices):
        PREPARED = "prepared", "Prepared"
        AUTOFILLED = "autofilled", "Autofilled - awaiting your review"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"
        COMPLETED = "completed", "Completed (you confirmed submission)"

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="attempts")
    attempt_no = models.PositiveSmallIntegerField(default=1)
    state = models.CharField(max_length=12, choices=State.choices, default=State.PREPARED)
    host = models.CharField(max_length=120, blank=True)
    fields_filled = models.JSONField(default=list, blank=True)
    fields_skipped = models.JSONField(default=list, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-attempt_no"]
        constraints = [models.UniqueConstraint(fields=["application", "attempt_no"], name="uniq_attempt_no")]
