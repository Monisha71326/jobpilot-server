import secrets

from django.conf import settings
from django.db import models


def new_autofill_key() -> str:
    return secrets.token_urlsafe(32)


class Profile(models.Model):
    class RemotePref(models.TextChoices):
        ANY = "any", "Any"
        REMOTE = "remote", "Remote only"
        HYBRID = "hybrid", "Hybrid"
        ONSITE = "onsite", "On-site"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    headline = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=120, blank=True)
    summary = models.TextField(blank=True)
    years_experience = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    skills = models.JSONField(default=list, blank=True)
    desired_roles = models.JSONField(default=list, blank=True)
    desired_locations = models.JSONField(default=list, blank=True)
    remote_preference = models.CharField(max_length=10, choices=RemotePref.choices, default=RemotePref.ANY)
    links = models.JSONField(default=dict, blank=True)  # {"linkedin": "...", "github": "...", "portfolio": "..."}
    notice_period_days = models.PositiveIntegerField(null=True, blank=True)
    plan = models.ForeignKey("core.Plan", null=True, blank=True, on_delete=models.SET_NULL, related_name="profiles")
    # Scoped, read-only key used ONLY by the browser autofill extension; regenerate anytime.
    autofill_key = models.CharField(max_length=64, unique=True, default=new_autofill_key)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile<{self.user_id}>"
