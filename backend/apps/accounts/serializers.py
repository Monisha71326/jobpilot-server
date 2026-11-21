from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.core.skills import normalize_skill

from .models import Profile

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    first_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=60, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        validate_password(attrs["password"], User(username=attrs["email"], email=attrs["email"]))
        return attrs

    def create(self, validated):
        return User.objects.create_user(
            username=validated["email"],
            email=validated["email"],
            password=validated["password"],
            first_name=validated.get("first_name", ""),
            last_name=validated.get("last_name", ""),
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "headline", "phone", "location", "summary", "years_experience", "skills", "desired_roles",
            "desired_locations", "remote_preference", "links", "notice_period_days", "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def _clean_list(self, value, max_items=60):
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            raise serializers.ValidationError("Must be a list of strings.")
        out, seen = [], set()
        for v in value:
            v = v.strip()[:80]
            if v and v.lower() not in seen:
                seen.add(v.lower())
                out.append(v)
        return out[:max_items]

    def validate_skills(self, value):
        return [normalize_skill(s) for s in self._clean_list(value)]

    def validate_desired_roles(self, value):
        return self._clean_list(value, 15)

    def validate_desired_locations(self, value):
        return self._clean_list(value, 15)

    def validate_years_experience(self, value):
        if value < 0 or value > 60:
            raise serializers.ValidationError("Enter a value between 0 and 60.")
        return value

    def validate_links(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Must be an object.")
        out = {}
        for k, v in value.items():
            if k not in {"linkedin", "github", "portfolio", "website"} or not isinstance(v, str):
                continue
            v = v.strip()
            if v and not v.lower().startswith(("http://", "https://")):
                raise serializers.ValidationError(f"{k} must start with http:// or https://")
            out[k] = v[:300]
        return out


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "is_staff", "date_joined", "profile"]
        read_only_fields = ["id", "email", "is_staff", "date_joined"]


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False, min_length=8)
