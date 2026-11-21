from django.urls import path

from . import views as v

urlpatterns = [
    path("dashboard/", v.DashboardView.as_view()),
    path("applications/", v.ApplicationListView.as_view()),
    path("applications/<int:pk>/", v.ApplicationDetailView.as_view()),
    path("applications/<int:pk>/move/", v.MoveView.as_view()),
    path("applications/<int:pk>/prepare/", v.PrepareView.as_view()),
    path("applications/<int:pk>/review/", v.ReviewView.as_view()),
    path("applications/<int:pk>/confirm-submitted/", v.ConfirmSubmittedView.as_view()),
    path("applications/<int:pk>/attempts/<int:attempt_id>/<slug:action>/", v.AttemptActionView.as_view()),
    path("reminders/", v.ReminderListView.as_view()),
    path("reminders/<int:pk>/", v.ReminderDetailView.as_view()),
    path("writing/generate/", v.GenerateTextView.as_view()),
    path("autofill/profile/", v.AutofillProfileView.as_view()),
    path("autofill/report/", v.AutofillReportView.as_view()),
]
