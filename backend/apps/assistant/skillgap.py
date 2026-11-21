"""Skill gap analysis and learning roadmap generation (deterministic; local AI only adds optional narrative)."""
from apps.core import ai
from apps.core.skills import SOFT, extract_skills, resources_for

from .roles import EFFORT_HOURS, ROLE_SKILLS, match_role


def user_skills(user) -> set[str]:
    skills = set(user.profile.skills or [])
    for r in user.resumes.all():
        skills.update(r.skills or [])
    return skills


def required_for(*, role: str = "", job=None) -> tuple[str, list[str]]:
    if job is not None:
        skills = job.skills or extract_skills(f"{job.title}\n{job.description}")
        return job.title, skills
    key = match_role(role)
    if key:
        return key, ROLE_SKILLS[key]
    return role, extract_skills(role)


def build_roadmap(missing: list[str], hours_per_week: int = 8) -> dict:
    phases, week = [], 1
    ordered = [s for s in missing if s not in SOFT] + [s for s in missing if s in SOFT]
    i = 0
    while i < len(ordered):
        chunk, hours = [], 0
        while i < len(ordered) and (not chunk or hours + EFFORT_HOURS.get(ordered[i], 20) <= hours_per_week * 3):
            chunk.append(ordered[i])
            hours += EFFORT_HOURS.get(ordered[i], 20)
            i += 1
        weeks = max(1, round(hours / hours_per_week))
        phases.append({
            "title": f"Phase {len(phases) + 1}: {', '.join(chunk)}",
            "weeks": f"Weeks {week}-{week + weeks - 1}" if weeks > 1 else f"Week {week}",
            "skills": chunk,
            "est_hours": hours,
            "milestone": f"Build and publish a small project that uses {' and '.join(chunk[:2])}; add it to your resume with a measurable result.",
            "resources": {s: resources_for(s) for s in chunk},
        })
        week += weeks
    return {"phases": phases, "total_hours": sum(p["est_hours"] for p in phases), "total_weeks": week - 1, "hours_per_week": hours_per_week}


def analyze(user, *, role: str = "", job=None, hours_per_week: int = 8, with_ai: bool = False) -> dict:
    label, required = required_for(role=role, job=job)
    have_set = user_skills(user)
    have = [s for s in required if s in have_set]
    missing = [s for s in required if s not in have_set]
    out = {
        "target": label, "required": required, "have": have, "missing": missing,
        "coverage_pct": round(100 * len(have) / len(required)) if required else None,
        "roadmap": build_roadmap(missing, hours_per_week),
        "known_role": label in ROLE_SKILLS,
        "note": None if required else "Could not detect required skills. Try a common role name like 'Backend Developer' or pick a job.",
        "ai": None,
    }
    if with_ai and required:
        prompt = (
            f"Target: {label}. Skills the candidate already has: {', '.join(have) or 'none listed'}. Missing: {', '.join(missing) or 'none'}.\n"
            "Write a short, encouraging study plan (max 150 words) ordering the missing skills and suggesting one portfolio project. No made-up links."
        )
        fb = "Focus on the missing skills in the order listed in the roadmap and finish each phase with a small project."
        out["ai"] = ai.ask([{"role": "user", "content": prompt}], system="You are a practical career mentor.", fallback=fb, max_tokens=350).as_dict()
    return out
