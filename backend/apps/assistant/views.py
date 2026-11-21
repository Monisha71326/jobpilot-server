from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.quota import consume
from apps.core.skills import extract_skills
from apps.jobs.models import Job
from apps.resumes.models import Resume

from . import chat, interview, skillgap
from .models import AIConversation, AIMessage, CareerGoal, InterviewAnswer, InterviewSession


def primary_resume(user):
    return Resume.objects.filter(user=user, is_primary=True).first() or Resume.objects.filter(user=user).first()


# ----------------------------------------------------------------------------- chat
def conv_dict(c: AIConversation, with_messages=False) -> dict:
    d = {"id": c.id, "title": c.title, "job_id": c.job_id, "updated_at": c.updated_at}
    if with_messages:
        d["messages"] = [{"id": m.id, "role": m.role, "content": m.content, "engine": m.engine, "created_at": m.created_at} for m in c.messages.all()]
    return d


class ConversationListView(APIView):
    def get(self, request):
        return Response([conv_dict(c) for c in AIConversation.objects.filter(user=request.user)[:50]])

    def post(self, request):
        job = None
        if request.data.get("job_id"):
            job = get_object_or_404(Job.objects.visible_to(request.user), pk=request.data["job_id"])
        c = AIConversation.objects.create(user=request.user, title=str(request.data.get("title") or "New chat")[:120], job=job)
        return Response(conv_dict(c, True), status=201)


class ConversationDetailView(APIView):
    def get(self, request, pk):
        return Response(conv_dict(get_object_or_404(AIConversation, pk=pk, user=request.user), True))

    def delete(self, request, pk):
        get_object_or_404(AIConversation, pk=pk, user=request.user).delete()
        return Response(status=204)


class MessageView(APIView):
    throttle_scope = "ai"

    def post(self, request, pk):
        c = get_object_or_404(AIConversation, pk=pk, user=request.user)
        text = str(request.data.get("content", "")).strip()
        if not text:
            return Response({"content": ["Write a message first."]}, status=400)
        if len(text) > 4000:
            return Response({"content": ["Message is too long (max 4000 characters)."]}, status=400)
        consume(request.user, "ai_chat")
        history = [{"role": m.role, "content": m.content} for m in c.messages.order_by("-created_at", "-id")[:10]][::-1]
        user_msg = AIMessage.objects.create(conversation=c, role="user", content=text)
        res = chat.reply(request.user, history, text, primary_resume(request.user), c.job)
        bot = AIMessage.objects.create(conversation=c, role="assistant", content=res.text, engine=res.engine)
        if c.title == "New chat":
            c.title = text[:60]
        c.save()
        return Response({
            "user_message": {"id": user_msg.id, "role": "user", "content": text},
            "assistant_message": {"id": bot.id, "role": "assistant", "content": bot.content, "engine": bot.engine, "note": res.note},
        }, status=201)


# ----------------------------------------------------------------------------- interviews
def session_dict(s: InterviewSession, detail=False) -> dict:
    answers = list(s.answers.all())
    d = {
        "id": s.id, "role_title": s.role_title, "kind": s.kind, "status": s.status, "engine": s.engine,
        "total": len(s.questions), "answered": len(answers), "started_at": s.started_at, "completed_at": s.completed_at,
        "summary": s.summary, "job_id": s.job_id,
    }
    if detail:
        d["questions"] = s.questions
        d["answers"] = [{"question_index": a.question_index, "answer": a.answer_text, "score": a.score, "feedback": a.feedback} for a in answers]
        d["next_index"] = next((q["id"] for q in s.questions if q["id"] not in {a.question_index for a in answers}), None)
    return d


class InterviewListView(APIView):
    def get(self, request):
        qs = InterviewSession.objects.filter(user=request.user).prefetch_related("answers")[:50]
        return Response([session_dict(s) for s in qs])

    @transaction.atomic
    def post(self, request):
        d, user = request.data, request.user
        job = get_object_or_404(Job.objects.visible_to(user), pk=d["job_id"]) if d.get("job_id") else None
        role = (job.title if job else str(d.get("role") or "").strip()) or (user.profile.desired_roles[0] if user.profile.desired_roles else "")
        if not role:
            return Response({"detail": "Enter the role you are interviewing for, or pick a job."}, status=400)
        kind = d.get("kind") if d.get("kind") in ("behavioral", "technical", "mixed") else "mixed"
        count = max(3, min(10, int(d.get("count") or 5))) if str(d.get("count") or "5").isdigit() else 5
        consume(user, "ai_interview")
        skills = (job.skills if job else None) or extract_skills(role) or list(user.profile.skills[:8])
        questions, engine = interview.generate_questions(role, job, skills, kind, count)
        s = InterviewSession.objects.create(user=user, job=job, role_title=role[:160], kind=kind, questions=questions, engine=engine)
        return Response(session_dict(s, True), status=201)


class InterviewDetailView(APIView):
    def get(self, request, pk):
        s = get_object_or_404(InterviewSession.objects.prefetch_related("answers"), pk=pk, user=request.user)
        return Response(session_dict(s, True))

    def delete(self, request, pk):
        get_object_or_404(InterviewSession, pk=pk, user=request.user).delete()
        return Response(status=204)


class InterviewAnswerView(APIView):
    throttle_scope = "ai"

    @transaction.atomic
    def post(self, request, pk):
        s = get_object_or_404(InterviewSession, pk=pk, user=request.user)
        if s.status == "completed":
            return Response({"detail": "This session is finished."}, status=409)
        answer = str(request.data.get("answer", "")).strip()
        if len(answer) < 3:
            return Response({"answer": ["Write or dictate your answer first."]}, status=400)
        answer = answer[:5000]
        try:
            idx = int(request.data.get("question_index"))
        except (TypeError, ValueError):
            return Response({"question_index": ["Required."]}, status=400)
        q = next((x for x in s.questions if x["id"] == idx), None)
        if not q:
            return Response({"question_index": ["Unknown question."]}, status=400)
        if InterviewAnswer.objects.filter(session=s, question_index=idx).exists():
            return Response({"detail": "You already answered this question."}, status=409)
        consume(request.user, "ai_interview")
        ev = interview.evaluate(q, answer, s.role_title)
        InterviewAnswer.objects.create(session=s, question_index=idx, answer_text=answer, score=ev["score"], feedback=ev)
        done = s.answers.count() >= len(s.questions)
        if done:
            s.status, s.completed_at = "completed", timezone.now()
            s.summary = interview.summarize(s, list(s.answers.all()))
            s.save()
        return Response({"evaluation": ev, "completed": done, "summary": s.summary if done else None})


class InterviewFinishView(APIView):
    def post(self, request, pk):
        s = get_object_or_404(InterviewSession.objects.prefetch_related("answers"), pk=pk, user=request.user)
        if s.status != "completed":
            s.status, s.completed_at = "completed", timezone.now()
            s.summary = interview.summarize(s, list(s.answers.all()))
            s.save()
        return Response(session_dict(s, True))


# ----------------------------------------------------------------------------- skill gap + goals
class SkillGapView(APIView):
    throttle_scope = "ai"

    def post(self, request):
        d, user = request.data, request.user
        job = get_object_or_404(Job.objects.visible_to(user), pk=d["job_id"]) if d.get("job_id") else None
        role = str(d.get("role") or "").strip()[:120]
        if not job and not role:
            return Response({"detail": "Choose a target role or a job."}, status=400)
        hpw = max(2, min(40, int(d["hours_per_week"]))) if str(d.get("hours_per_week", "")).isdigit() else 8
        with_ai = bool(d.get("with_ai"))
        if with_ai:
            consume(user, "ai_roadmap")
        return Response(skillgap.analyze(user, role=role, job=job, hours_per_week=hpw, with_ai=with_ai))


class RolesView(APIView):
    def get(self, request):
        from .roles import ROLE_SKILLS

        return Response([{"role": r, "skills": s} for r, s in ROLE_SKILLS.items()])


def goal_dict(g: CareerGoal) -> dict:
    need = g.skills_needed or []
    done = [s for s in g.completed_skills if s in need]
    return {
        "id": g.id, "title": g.title, "target_role": g.target_role, "target_date": g.target_date, "status": g.status,
        "skills_needed": need, "completed_skills": done, "progress": round(100 * len(done) / len(need)) if need else 0,
        "roadmap": g.roadmap, "updated_at": g.updated_at,
    }


class GoalListView(APIView):
    def get(self, request):
        return Response([goal_dict(g) for g in CareerGoal.objects.filter(user=request.user)])

    def post(self, request):
        role = str(request.data.get("target_role", "")).strip()[:120]
        if not role:
            return Response({"target_role": ["Enter the role you are aiming for."]}, status=400)
        tdate = parse_date(str(request.data.get("target_date") or "")) if request.data.get("target_date") else None
        gap = skillgap.analyze(request.user, role=role)
        g = CareerGoal.objects.create(
            user=request.user, title=str(request.data.get("title") or f"Become a {gap['target']}")[:140], target_role=gap["target"][:120],
            target_date=tdate, skills_needed=gap["required"], completed_skills=gap["have"], roadmap=gap["roadmap"],
        )
        return Response(goal_dict(g), status=201)


class GoalDetailView(APIView):
    def patch(self, request, pk):
        g = get_object_or_404(CareerGoal, pk=pk, user=request.user)
        d = request.data
        if isinstance(d.get("completed_skills"), list):
            g.completed_skills = [str(s)[:60] for s in d["completed_skills"] if str(s) in g.skills_needed]
        if d.get("status") in CareerGoal.Status.values:
            g.status = d["status"]
        if "target_date" in d:
            g.target_date = parse_date(str(d["target_date"])) if d["target_date"] else None
        if d.get("title"):
            g.title = str(d["title"])[:140]
        g.save()
        return Response(goal_dict(g))

    def delete(self, request, pk):
        get_object_or_404(CareerGoal, pk=pk, user=request.user).delete()
        return Response(status=204)


class GoalRegenerateView(APIView):
    def post(self, request, pk):
        g = get_object_or_404(CareerGoal, pk=pk, user=request.user)
        gap = skillgap.analyze(request.user, role=g.target_role)
        g.skills_needed = gap["required"] or g.skills_needed
        g.completed_skills = sorted(set(g.completed_skills) | set(gap["have"]))
        g.roadmap = skillgap.build_roadmap([s for s in g.skills_needed if s not in g.completed_skills])
        g.save()
        return Response(goal_dict(g))
