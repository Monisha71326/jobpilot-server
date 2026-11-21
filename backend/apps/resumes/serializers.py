from rest_framework import serializers

from .models import Resume, ResumeVersion


class ResumeSerializer(serializers.ModelSerializer):
    latest_version = serializers.SerializerMethodField()
    has_file = serializers.SerializerMethodField()
    analysis_score = serializers.SerializerMethodField()

    class Meta:
        model = Resume
        fields = [
            "id", "title", "source", "original_filename", "file_type", "page_count", "skills", "is_primary",
            "analysis_at", "analysis_score", "has_file", "latest_version", "created_at", "updated_at",
        ]
        read_only_fields = [f for f in fields if f != "title"]

    def get_latest_version(self, obj):
        v = max(obj.versions.all(), key=lambda x: x.version_no, default=None)
        return v.version_no if v else None

    def get_has_file(self, obj):
        return bool(obj.file)

    def get_analysis_score(self, obj):
        return obj.analysis.get("score") if obj.analysis else None


class ResumeDetailSerializer(ResumeSerializer):
    class Meta(ResumeSerializer.Meta):
        fields = ResumeSerializer.Meta.fields + ["parsed_data", "analysis"]
        read_only_fields = [f for f in fields if f != "title"]


class ResumeVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResumeVersion
        fields = ["version_no", "template", "content", "note", "created_at"]
        read_only_fields = fields
