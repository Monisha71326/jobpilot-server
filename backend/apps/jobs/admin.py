from django.contrib import admin

from .models import Job, JobSource, SavedJob, TrackedBoard


@admin.register(JobSource)
class JobSourceAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "kind", "is_active", "min_refresh_minutes", "last_fetched_at")
    list_filter = ("kind", "is_active")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "source", "is_remote", "is_active", "posted_at", "last_checked_at")
    list_filter = ("source", "is_remote", "is_active")
    search_fields = ("title", "company")
    readonly_fields = ("fingerprint", "skills_text", "first_seen_at")


admin.site.register(SavedJob)
admin.site.register(TrackedBoard)
