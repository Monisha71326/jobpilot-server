from django.urls import path

from . import views as v

urlpatterns = [
    path("assistant/conversations/", v.ConversationListView.as_view()),
    path("assistant/conversations/<int:pk>/", v.ConversationDetailView.as_view()),
    path("assistant/conversations/<int:pk>/messages/", v.MessageView.as_view()),
    path("interviews/", v.InterviewListView.as_view()),
    path("interviews/<int:pk>/", v.InterviewDetailView.as_view()),
    path("interviews/<int:pk>/answer/", v.InterviewAnswerView.as_view()),
    path("interviews/<int:pk>/finish/", v.InterviewFinishView.as_view()),
    path("skills/gap/", v.SkillGapView.as_view()),
    path("skills/roles/", v.RolesView.as_view()),
    path("goals/", v.GoalListView.as_view()),
    path("goals/<int:pk>/", v.GoalDetailView.as_view()),
    path("goals/<int:pk>/regenerate/", v.GoalRegenerateView.as_view()),
]
