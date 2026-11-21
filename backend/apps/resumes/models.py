import uuid

from django.conf import settings
from django.db import models


def resume_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    # Random server-side name: never trust the client's filename for storage.
    return f"resumes/{instance.user_id}/{uuid.uuid4().hex}.{ext}"


class Resume(models.Model):
    class Source(models.TextChoices):
        UPLOAD = "upload", "Uploaded file"
        BUILDER = "builder", "Built in app"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes")
    title = models.CharField(max_length=120)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.UPLOAD)
    file = models.FileField(upload_to=resume_upload_path, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    file_type = models.CharField(max_length=10, blank=True)  # pdf | docx
    page_count = models.PositiveSmallIntegerField(default=0)
    parsed_text = models.TextField(blank=True)
    parsed_data = models.JSONField(default=dict, blank=True)
    skills = models.JSONField(default=list, blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    analysis_at = models.DateTimeField(null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "-updated_at"]
        indexes = [models.Index(fields=["user", "-updated_at"])]
        constraints = [
            models.UniqueConstraint(fields=["user"], condition=models.Q(is_primary=True), name="uniq_primary_resume_per_user"),
        ]

    def __str__(self):
        return f"{self.title} ({self.user_id})"

    def search_text(self) -> str:
        """Text used for matching: parsed upload text, or the builder's latest version flattened."""
        if self.parsed_text:
            return self.parsed_text
        v = self.versions.order_by("-version_no").first()
        if v:
            from .builder import flatten_content

            return flatten_content(v.content)
        return ""


class ResumeVersion(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="versions")
    version_no = models.PositiveIntegerField()
    template = models.CharField(max_length=20, default="classic")
    content = models.JSONField(default=dict)
    note = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_no"]
        constraints = [models.UniqueConstraint(fields=["resume", "version_no"], name="uniq_resume_version_no")]
