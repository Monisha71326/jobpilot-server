from django.conf import settings
from django.db import models


class AIConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=120, default="New chat")
    job = models.ForeignKey("jobs.Job", null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "-updated_at"])]


class AIMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    engine = models.CharField(max_length=10, blank=True)  # "ollama" | "rules" for assistant messages
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["conversation", "created_at"])]


class InterviewSession(models.Model):
    class Kind(models.TextChoices):
        BEHAVIORAL = "behavioral", "Behavioral"
        TECHNICAL = "technical", "Technical"
        MIXED = "mixed", "Mixed"

    class Status(models.TextChoices):
        ACTIVE = "active", "In progress"
        COMPLETED = "completed", "Completed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interviews")
    job = models.ForeignKey("jobs.Job", null=True, blank=True, on_delete=models.SET_NULL, related_name="interviews")
    role_title = models.CharField(max_length=160)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.MIXED)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    questions = models.JSONField(default=list)
    summary = models.JSONField(default=dict, blank=True)
    engine = models.CharField(max_length=10, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["user", "-started_at"])]


class InterviewAnswer(models.Model):
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name="answers")
    question_index = models.PositiveSmallIntegerField()
    answer_text = models.TextField()
    score = models.PositiveSmallIntegerField()
    feedback = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["question_index"]
        constraints = [models.UniqueConstraint(fields=["session", "question_index"], name="uniq_answer_per_question")]


class CareerGoal(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ACHIEVED = "achieved", "Achieved"
        PAUSED = "paused", "Paused"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="career_goals")
    title = models.CharField(max_length=140)
    target_role = models.CharField(max_length=120)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    skills_needed = models.JSONField(default=list, blank=True)
    completed_skills = models.JSONField(default=list, blank=True)
    roadmap = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-updated_at"]
        indexes = [models.Index(fields=["user", "status"])]
