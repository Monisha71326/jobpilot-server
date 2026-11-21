"""Role skill profiles (priority-ordered) and approximate learning effort. General guidance, not market data."""
import re

ROLE_SKILLS: dict[str, list[str]] = {
    "Backend Developer": ["Python", "SQL", "REST APIs", "Git", "PostgreSQL", "Docker", "Testing", "System Design", "Linux", "Redis"],
    "Frontend Developer": ["JavaScript", "HTML", "CSS", "React", "TypeScript", "Git", "Testing", "REST APIs", "Tailwind CSS", "UI/UX"],
    "Full-Stack Developer": ["JavaScript", "TypeScript", "React", "Python", "Django", "SQL", "REST APIs", "Git", "Docker", "Testing"],
    "Data Analyst": ["SQL", "Excel", "Python", "Pandas", "Data Visualization", "Data Analysis", "Communication"],
    "Data Scientist": ["Python", "Pandas", "NumPy", "scikit-learn", "Machine Learning", "SQL", "Data Visualization", "Data Analysis"],
    "Machine Learning Engineer": ["Python", "Machine Learning", "PyTorch", "scikit-learn", "Docker", "SQL", "Deep Learning", "NLP", "AWS"],
    "DevOps Engineer": ["Linux", "Docker", "Kubernetes", "CI/CD", "Git", "Terraform", "AWS", "Python", "Networking"],
    "QA Engineer": ["Testing", "Python", "SQL", "Jira", "CI/CD", "Git", "REST APIs", "Agile"],
    "Mobile Developer": ["Flutter", "React Native", "Android", "Git", "REST APIs", "UI/UX", "Testing"],
    "Product Manager": ["Product Management", "Communication", "Agile", "Data Analysis", "Jira", "UI/UX", "Leadership"],
    "UI/UX Designer": ["Figma", "UI/UX", "Communication", "HTML", "CSS"],
    "Digital Marketer": ["SEO", "Digital Marketing", "Content Writing", "Data Analysis", "Communication"],
}

# Rough hours to reach job-ready basics for a motivated beginner. Intentionally approximate.
EFFORT_HOURS = {
    "Python": 60, "JavaScript": 60, "TypeScript": 25, "React": 40, "Django": 40, "SQL": 25, "PostgreSQL": 15, "Git": 8,
    "Docker": 15, "Kubernetes": 40, "Linux": 25, "REST APIs": 15, "Testing": 20, "System Design": 50, "Machine Learning": 80,
    "PyTorch": 40, "Pandas": 20, "NumPy": 10, "Excel": 15, "HTML": 12, "CSS": 20, "Tailwind CSS": 10, "AWS": 40, "Terraform": 25,
}


def match_role(text: str) -> str | None:
    t = re.sub(r"[^a-z0-9/+ ]", " ", (text or "").lower())
    best, best_n = None, 0
    for role in ROLE_SKILLS:
        words = [w for w in re.split(r"\W+", role.lower()) if w and w not in {"developer", "engineer"}]
        n = sum(1 for w in words if w in t)
        if role.lower() in t:
            n += 5
        if n > best_n:
            best, best_n = role, n
    if best_n:
        return best
    if re.search(r"\b(software|programmer|developer|engineer|sde)\b", t):
        return "Full-Stack Developer"
    return None
