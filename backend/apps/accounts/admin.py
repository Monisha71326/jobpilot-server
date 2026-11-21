from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "headline", "location", "years_experience", "remote_preference", "updated_at")
    search_fields = ("user__email", "headline", "location")
    exclude = ("autofill_key",)  # never show secrets in the admin
