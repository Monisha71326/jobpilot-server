import hashlib
import re

from django.conf import settings
from django.db import models
from django.db.models import Q


class JobSource(models.Model):
    class Kind(models.TextChoices):
        API = "api", "Official/public API"
        BOARD = "board", "Company job board API"
        USER = "user", "User-provided"
        DEMO = "demo", "Demo data (not real)"

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    base_url = models.URLField(blank=True)
    terms_url = models.URLField(blank=True)
    attribution = models.CharField(max_length=200, blank=True)
    min_refresh_minutes = models.PositiveIntegerField(default=60)
    is_active = models.BooleanField(default=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class JobQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Public/shared jobs plus the jobs this user imported themselves. Never other users' imports."""
        return self.filter(Q(added_by__isnull=True) | Q(added_by=user))


def normalize_fp(title: str, company: str, location: str = "") -> str:
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()  # noqa: E731
    return hashlib.sha1(f"{norm(title)}|{norm(company)}|{norm(location)}".encode()).hexdigest()


class Job(models.Model):
    source = models.ForeignKey(JobSource, on_delete=models.PROTECT, related_name="jobs")
    external_id = models.CharField(max_length=120)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="imported_jobs")
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=160)
    location = models.CharField(max_length=160, blank=True)
    is_remote = models.BooleanField(default=False)
    employment_type = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    skills_text = models.TextField(blank=True, editable=False)  # "|python|django|" for portable skill filtering
    min_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    max_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    salary_text = models.CharField(max_length=120, blank=True)
    apply_url = models.URLField(max_length=600, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_checked_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    fingerprint = models.CharField(max_length=40, db_index=True, editable=False, blank=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-posted_at", "-first_seen_at"]
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], condition=Q(added_by__isnull=True), name="uniq_shared_job"),
            models.UniqueConstraint(fields=["source", "external_id", "added_by"], condition=Q(added_by__isnull=False), name="uniq_user_job"),
        ]
        indexes = [
            models.Index(fields=["is_active", "-posted_at"]),
            models.Index(fields=["is_remote", "is_active"]),
            models.Index(fields=["title"]),
            models.Index(fields=["company"]),
        ]

    def save(self, *args, **kwargs):
        self.skills_text = "|" + "|".join(s.lower() for s in (self.skills or [])) + "|" if self.skills else ""
        self.fingerprint = normalize_fp(self.title, self.company, self.location)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} @ {self.company}"


class JobMatch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_matches")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="matches")
    resume = models.ForeignKey("resumes.Resume", on_delete=models.CASCADE, related_name="matches")
    score = models.PositiveSmallIntegerField()
    breakdown = models.JSONField(default=dict)
    computed_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "job", "resume"], name="uniq_match_user_job_resume")]
        indexes = [models.Index(fields=["user", "resume", "-score"])]


class SavedJob(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_jobs")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="saved_by")
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "job"], name="uniq_saved_user_job")]


class TrackedBoard(models.Model):
    """A company board (Greenhouse/Lever token) a user chose to follow. Fetched only when the user presses Refresh."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tracked_boards")
    source = models.ForeignKey(JobSource, on_delete=models.CASCADE)
    token = models.CharField(max_length=80)
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "source", "token"], name="uniq_tracked_board")]
