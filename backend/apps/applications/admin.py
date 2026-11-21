from django.contrib import admin

from .models import Application, ApplicationActivity, ApplyAttempt, Reminder


class ActivityInline(admin.TabularInline):
    model = ApplicationActivity
    extra = 0
    readonly_fields = ("kind", "message", "created_at")
    can_delete = False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("job_title", "company", "user", "status", "submission_confirmed_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("job_title", "company", "user__email")
    exclude = ("cover_letter", "notes")  # private user content
    inlines = [ActivityInline]


admin.site.register(Reminder)
admin.site.register(ApplyAttempt)
