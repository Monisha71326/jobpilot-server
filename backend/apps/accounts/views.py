from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import ai
from apps.core.models import Notification
from apps.core.quota import usage_summary

from .models import Profile, new_autofill_key
from .serializers import (
    LoginSerializer, PasswordChangeSerializer, ProfileSerializer, RegisterSerializer, UserSerializer,
)

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "auth"

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        token, _ = Token.objects.get_or_create(user=user)
        Notification.objects.create(
            user=user, kind="system", title="Welcome to JobPilot",
            body="Start by uploading your resume and completing your profile.", link="/resumes",
        )
        return Response({"token": token.key, "user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "auth"

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = authenticate(username=ser.validated_data["email"].strip().lower(), password=ser.validated_data["password"])
        if not user or not user.is_active:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        u = request.user
        for f in ("first_name", "last_name"):
            if f in request.data:
                setattr(u, f, str(request.data[f])[:60])
        u.save(update_fields=["first_name", "last_name"])
        return Response(UserSerializer(u).data)

    def delete(self, request):
        """Delete account and all associated data (privacy). Requires password confirmation."""
        if not request.user.check_password(str(request.data.get("password", ""))):
            return Response({"detail": "Password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        # Remove stored resume files from disk before DB rows disappear.
        from apps.resumes.models import Resume

        for r in Resume.objects.filter(user=request.user):
            if r.file:
                r.file.delete(save=False)
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer

    def get_object(self):
        return Profile.objects.get_or_create(user=self.request.user)[0]


class PasswordChangeView(APIView):
    def post(self, request):
        ser = PasswordChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not request.user.check_password(ser.validated_data["old_password"]):
            return Response({"detail": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(ser.validated_data["new_password"], request.user)
        except DjangoValidationError as e:
            return Response({"new_password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(ser.validated_data["new_password"])
        request.user.save()
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        return Response({"token": token.key})


class AutofillKeyView(APIView):
    """Show / regenerate the scoped key used by the browser extension."""

    def get(self, request):
        return Response({"autofill_key": request.user.profile.autofill_key})

    def post(self, request):
        p = request.user.profile
        p.autofill_key = new_autofill_key()
        p.save(update_fields=["autofill_key"])
        return Response({"autofill_key": p.autofill_key})


class UsageView(APIView):
    def get(self, request):
        return Response({"usage": usage_summary(request.user), "billing_enabled": False})


class AIStatusView(APIView):
    def get(self, request):
        return Response(ai.status(force=request.query_params.get("refresh") == "1"))


class NotificationListView(APIView):
    def get(self, request):
        qs = Notification.objects.filter(user=request.user)[:50]
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({
            "unread": unread,
            "results": [
                {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
                 "is_read": n.is_read, "created_at": n.created_at}
                for n in qs
            ],
        })

    def post(self, request):
        """Mark all (or the given ids) as read."""
        ids = request.data.get("ids")
        qs = Notification.objects.filter(user=request.user, is_read=False)
        if isinstance(ids, list):
            qs = qs.filter(id__in=[i for i in ids if isinstance(i, int)])
        qs.update(is_read=True)
        return Response({"ok": True})
