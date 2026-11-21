from django.contrib import admin

from .models import AIConversation, CareerGoal, InterviewSession


@admin.register(AIConversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "updated_at")
    exclude = ()
    readonly_fields = ("user", "job")


@admin.register(InterviewSession)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ("role_title", "user", "kind", "status", "started_at")
    list_filter = ("kind", "status")


admin.site.register(CareerGoal)
