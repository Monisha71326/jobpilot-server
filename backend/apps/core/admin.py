from django.contrib import admin

from .models import Notification, Plan, UsageRecord


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "monthly_price_inr", "is_default", "is_active")


@admin.register(UsageRecord)
class UsageAdmin(admin.ModelAdmin):
    list_display = ("user", "feature", "day", "count")
    list_filter = ("feature", "day")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "title", "is_read", "created_at")
    list_filter = ("kind", "is_read")
