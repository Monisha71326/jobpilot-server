"""Deterministic resume analysis (ATS-style checks). Optional LLM suggestions are layered on top in views."""
import re

from apps.core.skills import extract_skills
from apps.core.textutil import tokens

ACTION_VERBS = set(
    """built developed designed implemented led managed created improved reduced increased optimized launched delivered automated
    architected migrated analyzed engineered deployed integrated mentored established streamlined drove owned shipped refactored
    coordinated negotiated achieved generated resolved trained scaled maintained tested collaborated researched wrote produced
    executed administered supported""".split()
)
WEAK_PHRASES = ["responsible for", "worked on", "helped with", "assisted in", "duties included", "tasked with", "involved in"]
NUMBER = re.compile(r"(\d+(\.\d+)?\s?%|[$₹€£]\s?\d|\b\d{2,}[kKmM]?\+?\b|\b\d+x\b)")
BULLET = re.compile(r"^\s*[-•*▪●◦]\s+(.*\S)")


def analyze(text: str, parsed: dict, *, page_count: int = 0, tables: int = 0, job_text: str = "") -> dict:
    words = len(text.split())
    lines = text.split("\n")
    bullets = [m.group(1) for l in lines if (m := BULLET.match(l))]
    first_words = [b.split()[0].lower().strip(",.:;") for b in bullets if b.split()]
    verb_hits = sum(1 for w in first_words if w in ACTION_VERBS)
    verb_ratio = verb_hits / len(bullets) if bullets else 0
    quantified = sum(1 for b in bullets if NUMBER.search(b))
    weak = [p for p in WEAK_PHRASES if p in text.lower()]
    sections = set(parsed.get("sections_found", []))
    skills = parsed.get("skills") or extract_skills(text)

    checks = []

    def add(cid, label, passed, weight, detail, fix=""):
        checks.append({"id": cid, "label": label, "passed": bool(passed), "weight": weight, "detail": detail, "fix": "" if passed else fix})

    add("email", "Email address present", parsed.get("email"), 8, parsed.get("email") or "No email found", "Add a professional email at the top.")
    add("phone", "Phone number present", parsed.get("phone"), 5, parsed.get("phone") or "No phone found", "Add a phone number recruiters can call.")
    add("links", "Professional link (LinkedIn/GitHub)", parsed.get("links"), 4, ", ".join(parsed.get("links", {}).values()) or "No profile links", "Add your LinkedIn or GitHub URL.")
    add("summary", "Summary or objective", "summary" in sections, 6, "Found" if "summary" in sections else "Missing", "Add a 2-3 line summary that names your target role and top skills.")
    add("experience", "Experience section", "experience" in sections, 12, "Found" if "experience" in sections else "Missing", "Add a clearly titled 'Experience' section (include internships/projects if you're a fresher).")
    add("education", "Education section", "education" in sections, 8, "Found" if "education" in sections else "Missing", "Add an 'Education' section.")
    add("skills_section", "Skills section", "skills" in sections, 8, "Found" if "skills" in sections else "Missing", "Add a 'Skills' section listing tools and technologies.")
    add("skill_count", "At least 8 recognizable skills", len(skills) >= 8, 8, f"{len(skills)} detected", "List more specific tools/technologies (e.g. 'PostgreSQL', not just 'databases').")
    add("length", "Length is 250-900 words", 250 <= words <= 900, 8, f"{words} words", "Aim for one page (fresher) to two pages (experienced).")
    if page_count:
        add("pages", "Two pages or fewer", page_count <= 2, 5, f"{page_count} page(s)", "Trim older or less relevant content to fit two pages.")
    add("bullets", "Uses bullet points", len(bullets) >= 5, 6, f"{len(bullets)} bullets", "Describe achievements in short bullet points.")
    add("verbs", "Bullets start with strong action verbs", verb_ratio >= 0.5, 8, f"{round(verb_ratio * 100)}% of bullets", "Start bullets with verbs like 'Built', 'Reduced', 'Led'.")
    add("metrics", "Quantified achievements", quantified >= 3, 10, f"{quantified} bullet(s) with numbers", "Add numbers: % improvement, users, time saved, revenue, team size.")
    add("weak", "Avoids weak phrases", not weak, 4, ", ".join(weak) or "None found", "Replace phrases like 'responsible for' with the result you achieved.")
    add("tables", "No tables/columns that confuse ATS", tables == 0, 4, f"{tables} table(s)", "Use a single-column layout; ATS systems often scramble tables.")

    total = sum(c["weight"] for c in checks)
    got = sum(c["weight"] for c in checks if c["passed"])
    score = round(100 * got / total) if total else 0
    out = {
        "score": score,
        "grade": "Excellent" if score >= 85 else "Good" if score >= 70 else "Needs work" if score >= 50 else "Weak",
        "checks": checks,
        "strengths": [c["label"] for c in checks if c["passed"]][:6],
        "improvements": [{"issue": c["label"], "fix": c["fix"]} for c in sorted(checks, key=lambda c: -c["weight"]) if not c["passed"]][:8],
        "stats": {"words": words, "bullets": len(bullets), "quantified_bullets": quantified, "skills": len(skills), "pages": page_count},
        "skills": skills,
    }
    if job_text:
        out["job_fit"] = keyword_coverage(text, job_text)
    return out


def keyword_coverage(resume_text: str, job_text: str) -> dict:
    job_skills = extract_skills(job_text)
    res_skills = set(extract_skills(resume_text))
    matched = [s for s in job_skills if s in res_skills]
    missing = [s for s in job_skills if s not in res_skills]
    rtok = set(tokens(resume_text))
    from collections import Counter

    jt = Counter(tokens(job_text))
    keywords = [w for w, _ in jt.most_common(40) if len(w) > 3][:25]
    kw_missing = [w for w in keywords if w not in rtok][:12]
    return {
        "skill_coverage_pct": round(100 * len(matched) / len(job_skills)) if job_skills else None,
        "matched_skills": matched,
        "missing_skills": missing,
        "missing_keywords": kw_missing,
    }
