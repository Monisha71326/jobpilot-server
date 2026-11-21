from django.contrib import admin

from .models import Resume, ResumeVersion


class VersionInline(admin.TabularInline):
    model = ResumeVersion
    extra = 0
    fields = ("version_no", "template", "note", "created_at")
    readonly_fields = fields
    can_delete = False


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "source", "file_type", "is_primary", "updated_at")
    list_filter = ("source", "file_type", "is_primary")
    search_fields = ("title", "user__email")
    # Resume text is private user data: keep it out of the admin form.
    exclude = ("parsed_text", "parsed_data", "analysis", "file")
    inlines = [VersionInline]
