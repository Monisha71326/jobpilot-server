"""Career assistant chat. Local LLM when available; otherwise a transparent rule-based helper."""
import re

from apps.core import ai

SYSTEM = (
    "You are JobPilot's career assistant for a job seeker. Be concise, practical and honest. Never invent facts about the user, "
    "employers or job openings. If you do not know something, say so. Never claim you applied to a job or sent a message. "
    "Do not give legal or financial guarantees. " + ai.UNTRUSTED_NOTE
)


def context_block(user, resume, job) -> str:
    p = user.profile
    lines = [
        f"Candidate: {user.first_name} {user.last_name}".strip(),
        f"Headline: {p.headline}", f"Location: {p.location}", f"Years of experience: {p.years_experience}",
        f"Skills: {', '.join(p.skills[:25])}", f"Target roles: {', '.join(p.desired_roles)}",
    ]
    block = "\n".join(l for l in lines if l.split(": ", 1)[-1].strip())
    if resume:
        block += "\n" + ai.wrap_untrusted("resume_excerpt", resume.search_text(), 2500)
    if job:
        block += f"\nJob being discussed: {job.title} at {job.company}\n" + ai.wrap_untrusted("job_description", job.description, 2500)
    return block


def rules_reply(user, text: str, resume) -> str:
    t = text.lower()
    if re.search(r"resume|cv\b", t):
        if not resume:
            return "Upload your resume on the Resumes page first. I can then score it for ATS-friendliness and suggest fixes."
        imp = (resume.analysis or {}).get("improvements") or []
        if imp:
            return "From your latest resume analysis, the top fixes are:\n" + "\n".join(f"- {i['fix']}" for i in imp[:4]) + "\n\nOpen Resumes -> Analyze to re-check after editing."
        return "Open Resumes and press Analyze to get a score and specific fixes. Start bullets with action verbs and add numbers (%, users, time saved)."
    if re.search(r"interview|question", t):
        return ("Interview tips: use the STAR format (Situation, Task, Action, Result), prepare 3 stories with measurable results, research the company, "
                "and prepare two questions to ask them. Try Interview Practice in the sidebar for mock questions with feedback.")
    if re.search(r"skill|learn|roadmap|gap|upskill", t):
        return "Open Skills & Goals, pick a target role (or a job) and I'll compare it with your resume skills and build a week-by-week roadmap with free resources."
    if re.search(r"salary|negotiat|ctc|offer", t):
        return ("Negotiation basics: research the market range for your role and city, anchor to the higher end of a realistic range, "
                "talk about value you bring, consider the full package (variable pay, notice period buyout, learning budget), and get the final offer in writing.")
    if re.search(r"cover letter|recruiter|message|follow", t):
        return "Open any job or application and use 'Generate' to draft a cover letter, recruiter message or follow-up. I only use facts from your resume, and you should edit before sending."
    if re.search(r"hello|hi\b|hey", t):
        return "Hi! I can help with your resume, job search strategy, interviews, cover letters and skill gaps. What would you like to work on?"
    return ("The local AI model isn't running, so I'm answering with built-in rules. I can still help with: resume fixes, interview tips, skill gaps and roadmaps, "
            "cover letters and salary negotiation basics. For free-form conversation, install Ollama (see README) and pick a small model - it costs nothing.")


def reply(user, history: list[dict], text: str, resume, job) -> ai.AIResult:
    system = SYSTEM + "\n\n" + context_block(user, resume, job)
    msgs = history[-10:] + [{"role": "user", "content": text}]
    return ai.ask(msgs, system=system, fallback=rules_reply(user, text, resume), temperature=0.5, max_tokens=600)
