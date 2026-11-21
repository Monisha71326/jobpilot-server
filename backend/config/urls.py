from django.contrib import admin
from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.views.defaults import page_not_found
from django.urls import include, path, re_path

from apps.accounts import views as acc
from apps.core import views as core

api = [
    path("health/", core.health),
    path("auth/register/", acc.RegisterView.as_view()),
    path("auth/login/", acc.LoginView.as_view()),
    path("auth/logout/", acc.LogoutView.as_view()),
    path("auth/password/", acc.PasswordChangeView.as_view()),
    path("me/", acc.MeView.as_view()),
    path("profile/", acc.ProfileView.as_view()),
    path("profile/autofill-key/", acc.AutofillKeyView.as_view()),
    path("usage/", acc.UsageView.as_view()),
    path("ai/status/", acc.AIStatusView.as_view()),
    path("notifications/", acc.NotificationListView.as_view()),
    path("admin-stats/", core.AdminStatsView.as_view()),
    path("", include("apps.resumes.urls")),
    path("", include("apps.jobs.urls")),
    path("", include("apps.applications.urls")),
    path("", include("apps.assistant.urls")),
]



def spa(request, path=""):
    """Serve the built React app for any non-API route so client-side routing (BrowserRouter) survives a refresh."""
    index = getattr(settings, "FRONTEND_DIST", None)
    index = index / "index.html" if index else None
    if not index or not index.exists():
        raise Http404("Frontend not built. Run `npm run build` in frontend/, or use the Vite dev server on :5173.")
    return FileResponse(open(index, "rb"), content_type="text/html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api)),
    re_path(r"^(?!api/|admin/|static/|assets/|media/)(?P<path>.*)$", spa),
]


def handler404(request, exception=None):
    """The API always answers in JSON, even for unknown URLs, so the frontend can show a readable message."""
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "Not found."}, status=404)
    return page_not_found(request, exception)
