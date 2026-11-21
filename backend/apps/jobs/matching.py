"""Explainable job matching. Deterministic and offline; optional local embeddings refine the text-similarity part."""
import re

from django.utils import timezone

from apps.core import ai
from apps.core.skills import SOFT, extract_skills
from apps.core.textutil import cosine, tokens, vec_cosine

from .models import JobMatch

WEIGHTS = {"skills": 50, "role": 15, "text": 15, "experience": 10, "location": 10}


def _title_sim(a: str, b: str) -> float:
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def candidate_context(user, resume) -> dict:
    p = user.profile
    skills = list(dict.fromkeys([*(resume.skills or []), *(p.skills or [])]))
    return {
        "skills": skills,
        "skill_set": set(skills),
        "text": resume.search_text(),
        "years": float(p.years_experience or (resume.parsed_data or {}).get("years_experience") or 0),
        "roles": p.desired_roles or ([p.headline] if p.headline else []),
        "locations": [x.lower() for x in [*(p.desired_locations or []), p.location] if x],
        "remote_pref": p.remote_preference,
    }


def score_job(ctx: dict, job, *, job_embedding=None, resume_embedding=None) -> dict:
    job_skills = job.skills or extract_skills(f"{job.title}\n{job.description}")
    matched = [s for s in job_skills if s in ctx["skill_set"]]
    missing = [s for s in job_skills if s not in ctx["skill_set"]]
    parts: list[dict] = []

    # 1. skills (weighted: soft skills count half)
    if job_skills:
        w = lambda s: 0.5 if s in SOFT else 1.0  # noqa: E731
        cov = sum(w(s) for s in matched) / sum(w(s) for s in job_skills)
        detail = f"You have {len(matched)} of {len(job_skills)} skills named in this posting."
    else:
        cov, detail = 0.5, "No specific skills were detected in this posting, so this is a neutral estimate."
    parts.append({"factor": "Skills", "max": WEIGHTS["skills"], "score": round(cov * WEIGHTS["skills"], 1), "detail": detail})

    # 2. role / title
    if ctx["roles"]:
        sim = max(_title_sim(job.title, r) for r in ctx["roles"])
        sim = min(1.0, sim * 1.6)  # token-overlap on short titles is naturally low
        rdetail = f"Compared with your target roles ({', '.join(ctx['roles'][:3])})."
    else:
        sim = min(1.0, cosine(job.title, ctx["text"][:1500]) * 2)
        rdetail = "No target roles set - compared the title with your resume. Add target roles in your profile for better results."
    parts.append({"factor": "Role fit", "max": WEIGHTS["role"], "score": round(sim * WEIGHTS["role"], 1), "detail": rdetail})

    # 3. overall text similarity
    if job_embedding is not None and resume_embedding is not None:
        t_sim, tdetail = min(1.0, max(0.0, vec_cosine(job_embedding, resume_embedding))), "Semantic similarity (local embedding model)."
    else:
        t_sim, tdetail = min(1.0, cosine(ctx["text"], job.description or job.title) / 0.4), "Keyword overlap between your resume and the job description."
    parts.append({"factor": "Resume relevance", "max": WEIGHTS["text"], "score": round(t_sim * WEIGHTS["text"], 1), "detail": tdetail})

    # 4. experience
    warnings: list[str] = []
    yrs, lo, hi = ctx["years"], job.min_experience, job.max_experience
    if lo is None:
        e, edetail = 0.7, "The posting doesn't state required experience."
    elif yrs >= lo:
        e, edetail = 1.0, f"You have ~{yrs:g} years; the job asks for {lo}+."
        if hi is not None and yrs > hi + 3:
            e, edetail = 0.7, f"You may be over-qualified (job targets {lo}-{hi} years, you have ~{yrs:g})."
    else:
        gap = lo - yrs
        e, edetail = max(0.0, 1 - 0.25 * gap), f"The job asks for {lo}+ years; your profile shows ~{yrs:g}."
        if gap >= 2:
            warnings.append(f"Experience gap: the posting asks for {lo}+ years and you list ~{yrs:g}.")
    parts.append({"factor": "Experience", "max": WEIGHTS["experience"], "score": round(e * WEIGHTS["experience"], 1), "detail": edetail})

    # 5. location / remote
    pref, jl = ctx["remote_pref"], (job.location or "").lower()
    loc_hit = any(l and (l in jl or jl in l) for l in ctx["locations"]) if jl else False
    if job.is_remote and pref in ("any", "remote", "hybrid"):
        l_s, ldetail = 1.0, "Remote role matches your preference."
    elif job.is_remote:
        l_s, ldetail = 0.6, "This is remote; you prefer on-site."
    elif pref == "remote":
        l_s, ldetail = 0.2, "This role is not remote and you prefer remote work."
        warnings.append("Not a remote role, but your preference is remote only.")
    elif loc_hit:
        l_s, ldetail = 1.0, f"Location '{job.location}' matches your preferred locations."
    elif not jl:
        l_s, ldetail = 0.5, "No location listed."
    else:
        l_s, ldetail = 0.3, f"Location '{job.location}' is not in your preferred locations."
        if ctx["locations"]:
            warnings.append(f"Location '{job.location}' is outside your preferred locations.")
    parts.append({"factor": "Location & remote", "max": WEIGHTS["location"], "score": round(l_s * WEIGHTS["location"], 1), "detail": ldetail})

    total = round(sum(p["score"] for p in parts))
    verdict = "Strong match" if total >= 75 else "Good match" if total >= 60 else "Partial match" if total >= 40 else "Low match"
    must_haves = [s for s in missing if s not in SOFT][:8]
    return {
        "score": min(100, total),
        "verdict": verdict,
        "factors": parts,
        "matched_skills": matched,
        "missing_skills": missing,
        "eligibility": {"likely_eligible": not warnings, "warnings": warnings},
        "tip": (f"Closing the gap on {', '.join(must_haves[:3])} would raise your score the most." if must_haves else "You cover the skills this posting names."),
    }


def ensure_matches(user, resume, jobs) -> dict[int, JobMatch]:
    """Compute/refresh stored matches for the given jobs against this resume. Returns {job_id: JobMatch}."""
    if resume is None:
        return {}
    ctx = candidate_context(user, resume)
    stale_before = max(resume.updated_at, user.profile.updated_at)
    existing = {m.job_id: m for m in JobMatch.objects.filter(user=user, resume=resume, job__in=jobs)}
    todo = [j for j in jobs if j.id not in existing or existing[j.id].computed_at < stale_before]
    if not todo:
        return existing
    r_emb = None
    embs: dict[int, list[float]] = {}
    batch = ai.embed([ctx["text"][:3000]] + [f"{j.title}\n{j.description[:1500]}" for j in todo[:60]]) if todo else None
    if batch and len(batch) == min(len(todo), 60) + 1:
        r_emb = batch[0]
        embs = {j.id: batch[i + 1] for i, j in enumerate(todo[:60])}
    now = timezone.now()
    for j in todo:
        res = score_job(ctx, j, job_embedding=embs.get(j.id), resume_embedding=r_emb if j.id in embs else None)
        m, _ = JobMatch.objects.update_or_create(
            user=user, job=j, resume=resume, defaults={"score": res["score"], "breakdown": res, "computed_at": now}
        )
        existing[j.id] = m
    return existing


def explain_for_one(user, resume, job) -> dict:
    return ensure_matches(user, resume, [job]).get(job.id).breakdown if resume else {}


_ = re  # keep import for future regex-based rules
