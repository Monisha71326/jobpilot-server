from django.urls import path

from . import views as v

urlpatterns = [
    path("resumes/", v.ResumeListView.as_view()),
    path("resumes/builder/", v.ResumeBuilderCreateView.as_view()),
    path("resume-templates/", v.TemplatesView.as_view()),
    path("resumes/<int:pk>/", v.ResumeDetailView.as_view()),
    path("resumes/<int:pk>/file/", v.ResumeFileView.as_view()),
    path("resumes/<int:pk>/set-primary/", v.SetPrimaryView.as_view()),
    path("resumes/<int:pk>/analyze/", v.AnalyzeView.as_view()),
    path("resumes/<int:pk>/to-builder/", v.ToBuilderView.as_view()),
    path("resumes/<int:pk>/versions/", v.VersionsView.as_view()),
    path("resumes/<int:pk>/export/", v.ExportView.as_view()),
    path("resumes/<int:pk>/apply-to-profile/", v.ApplyToProfileView.as_view()),
]
