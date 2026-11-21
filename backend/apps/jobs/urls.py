from django.urls import path

from . import views as v

urlpatterns = [
    path("jobs/", v.JobListView.as_view()),
    path("jobs/import/", v.JobImportView.as_view()),
    path("jobs/recommended/", v.RecommendedView.as_view()),
    path("jobs/sources/", v.SourcesView.as_view()),
    path("jobs/sources/<slug:slug>/refresh/", v.RefreshSourceView.as_view()),
    path("jobs/demo/", v.LoadDemoView.as_view()),
    path("jobs/boards/<int:pk>/", v.TrackedBoardDeleteView.as_view()),
    path("jobs/<int:pk>/", v.JobDetailView.as_view()),
    path("saved-jobs/", v.SavedJobsView.as_view()),
    path("saved-jobs/<int:job_id>/", v.SavedJobDetailView.as_view()),
]
