"""Cover letters, recruiter messages and follow-ups: local LLM with truthful template fallback."""
from apps.core import ai

KINDS = {
    "cover_letter": ("a cover letter (about 200-250 words)", 450),
    "recruiter_message": ("a short LinkedIn/email message to a recruiter (about 80 words)", 200),
    "follow_up": ("a polite follow-up email after applying (about 80 words)", 200),
    "thank_you": ("a thank-you email after an interview (about 100 words)", 250),
}
TONES = {"professional", "friendly", "confident", "concise"}


def _facts(user, resume, job, match) -> dict:
    p = user.profile
    name = f"{user.first_name} {user.last_name}".strip() or user.email.split("@")[0]
    matched = (match or {}).get("matched_skills", [])[:6] or (resume.skills[:6] if resume else [])
    return {
        "name": name, "headline": p.headline, "years": float(p.years_experience or 0), "skills": matched,
        "title": job.title if job else "the role", "company": job.company if job else "your company",
    }


def fallback_text(kind: str, f: dict) -> str:
    skills = ", ".join(f["skills"][:5])
    exp = f" With about {f['years']:g} years of experience," if f["years"] else ""
    skill_line = f" My background includes {skills}, which line up with what you are looking for." if skills else ""
    if kind == "recruiter_message":
        return (f"Hi, I came across the {f['title']} role at {f['company']} and I'm very interested.{skill_line} "
                f"I've applied and would love to share more about how I can contribute. Thank you for your time!\n\n{f['name']}")
    if kind == "follow_up":
        return (f"Hello,\n\nI recently applied for the {f['title']} position at {f['company']} and wanted to reaffirm my interest."
                f"{skill_line} I'd be glad to answer any questions. Thank you for your consideration.\n\nBest regards,\n{f['name']}")
    if kind == "thank_you":
        return (f"Hello,\n\nThank you for taking the time to speak with me about the {f['title']} role at {f['company']}. "
                f"I enjoyed learning more about the team and remain very interested.{skill_line}\n\nBest regards,\n{f['name']}")
    return (f"Dear Hiring Team at {f['company']},\n\nI am excited to apply for the {f['title']} position.{exp} I have built a foundation that fits this role."
            f"{skill_line}\n\n[Add one specific achievement here, with a number if you can - e.g. 'I reduced page load time by X%.']\n\n"
            f"I would welcome the chance to discuss how I can contribute to {f['company']}. Thank you for your time and consideration.\n\n"
            f"Sincerely,\n{f['name']}")


def generate(user, resume, job, match, kind="cover_letter", tone="professional", extra="") -> ai.AIResult:
    kind = kind if kind in KINDS else "cover_letter"
    tone = tone if tone in TONES else "professional"
    f = _facts(user, resume, job, match)
    what, max_tokens = KINDS[kind]
    prompt = (
        f"Write {what} in a {tone} tone for {f['name']}.\n"
        f"Role: {f['title']} at {f['company']}.\n"
        "Rules: use ONLY facts found in the resume text; never invent employers, degrees, numbers or skills. "
        "If an achievement would need a number you don't have, write a bracketed placeholder like [X%]. No placeholders for the company name. "
        "Output only the text, no preface.\n"
        + (f"Extra instructions from the candidate: {extra[:300]}\n" if extra else "")
        + (ai.wrap_untrusted("job_description", job.description, 3500) + "\n" if job else "")
        + (ai.wrap_untrusted("resume", resume.search_text(), 3500) if resume else "")
    )
    return ai.ask(
        [{"role": "user", "content": prompt}],
        system="You are an honest career writing assistant. " + ai.UNTRUSTED_NOTE,
        fallback=fallback_text(kind, f), temperature=0.5, max_tokens=max_tokens,
    )
