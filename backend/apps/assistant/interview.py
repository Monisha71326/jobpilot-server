"""Mock interview engine: question generation + answer evaluation. Heuristics always run; the local LLM adds depth."""
import json
import random
import re

from apps.core import ai
from apps.core.skills import extract_skills

BEHAVIORAL = [
    "Tell me about yourself and why you are interested in this role.",
    "Describe a time you faced a difficult deadline. What did you do and what was the result?",
    "Tell me about a time you disagreed with a teammate. How did you handle it?",
    "Describe a mistake you made at work or in a project. What did you learn?",
    "Give an example of a time you took initiative without being asked.",
    "Tell me about the project you are most proud of. What was your specific contribution?",
    "How do you prioritize when you have several urgent tasks?",
    "Describe a time you had to learn something new quickly.",
    "Tell me about a time you received critical feedback. How did you respond?",
    "Why should we hire you over other candidates?",
]

TECHNICAL = {
    "Python": ["Explain the difference between a list and a tuple, and when you would use each.", "What are decorators in Python and how would you write a simple one?", "How does Python manage memory, and what is the GIL?"],
    "JavaScript": ["Explain closures in JavaScript with an example.", "What is the difference between var, let and const?", "How does the event loop work, and what is the difference between a promise and async/await?"],
    "TypeScript": ["What are the benefits of TypeScript over JavaScript, and when would you use generics?"],
    "React": ["Explain how React's rendering works and when a component re-renders.", "What is the difference between state and props? When would you use useEffect?", "How would you optimize a slow React list of 10,000 items?"],
    "SQL": ["What is the difference between INNER JOIN and LEFT JOIN? Give an example.", "How do indexes work and when can they hurt performance?", "Explain the difference between WHERE and HAVING."],
    "PostgreSQL": ["What is a transaction, and what do ACID properties guarantee?"],
    "Django": ["Explain Django's request/response cycle.", "What is the ORM N+1 query problem and how do you avoid it in Django?", "How do migrations work in Django?"],
    "REST APIs": ["What makes an API RESTful? Explain idempotency of HTTP methods.", "How would you design pagination and error handling for a REST API?"],
    "Docker": ["What is the difference between an image and a container?", "How would you containerize a web app and keep the image small?"],
    "Git": ["Explain the difference between merge and rebase.", "How do you resolve a merge conflict?"],
    "Data Structures": ["When would you choose a hash map over an array? What is the time complexity of common operations?", "Explain how you would detect a cycle in a linked list."],
    "System Design": ["How would you design a URL shortener? Discuss storage, scaling and collisions."],
    "Machine Learning": ["Explain overfitting and three ways to reduce it.", "How do you choose evaluation metrics for an imbalanced classification problem?"],
    "Testing": ["What is the difference between unit and integration tests? What makes a test good?"],
    "Linux": ["How would you find which process is using a port and stop it?"],
    "Excel": ["Explain VLOOKUP vs INDEX/MATCH and when pivot tables help."],
    "Communication": ["How would you explain a complex technical topic to a non-technical stakeholder?"],
}
GENERIC_TECH = ["Walk me through a project where you used {skill}. What were the trade-offs?", "What are common mistakes people make with {skill}, and how do you avoid them?"]


def fallback_questions(role: str, skills: list[str], kind: str, count: int) -> list[dict]:
    rng = random.Random(f"{role}|{kind}|{','.join(skills)}")
    behav = [{"text": q, "type": "behavioral", "skill": ""} for q in BEHAVIORAL]
    tech = []
    for s in skills:
        qs = TECHNICAL.get(s) or [g.format(skill=s) for g in GENERIC_TECH]
        tech += [{"text": q, "type": "technical", "skill": s} for q in qs]
    rng.shuffle(behav)
    rng.shuffle(tech)
    first = behav[:1]  # always open with the classic intro question for realism
    rest_b, rest_t = behav[1:], tech
    if kind == "behavioral":
        picked = first + rest_b
    elif kind == "technical":
        picked = (rest_t or rest_b) + rest_b
    else:
        picked = first
        for a, b in zip(rest_t, rest_b):
            picked += [a, b]
        picked += rest_t[len(rest_b):] + rest_b[len(rest_t):]
    seen, out = set(), []
    for q in picked:
        if q["text"] not in seen:
            seen.add(q["text"])
            out.append(q)
    return [{"id": i, **q} for i, q in enumerate(out[:count])]


def generate_questions(role: str, job, skills: list[str], kind: str, count: int) -> tuple[list[dict], str]:
    jd = ai.wrap_untrusted("job_description", job.description, 3000) if job else ""
    prompt = (
        f"Create {count} {kind} interview questions for the role '{role}'. Candidate/job skills: {', '.join(skills[:12]) or 'general'}.\n"
        'Return JSON: {"questions":[{"text":"...","type":"behavioral|technical","skill":"..."}]}. Questions only, no answers.\n' + jd
    )
    data = ai.ask_json([{"role": "user", "content": prompt}], system="You are an experienced interviewer. " + ai.UNTRUSTED_NOTE, max_tokens=900)
    qs = []
    if data and isinstance(data.get("questions"), list):
        for q in data["questions"]:
            if isinstance(q, dict) and isinstance(q.get("text"), str) and 15 < len(q["text"]) < 400:
                qs.append({"id": len(qs), "text": q["text"].strip(), "type": q.get("type") if q.get("type") in ("behavioral", "technical") else "technical", "skill": str(q.get("skill", ""))[:40]})
    if len(qs) >= min(count, 3):
        return qs[:count], "ollama"
    return fallback_questions(role, skills, kind, count), "rules"


STAR = {
    "situation": r"\b(when|while|at|during|in my|our team|the project|situation|context|faced|challenge)\b",
    "task": r"\b(responsible|goal|objective|needed to|had to|task|assigned|aimed)\b",
    "action": r"\b(i (built|created|designed|wrote|led|decided|implemented|organized|analyzed|proposed|fixed|developed|set up|worked)|i then|so i|my approach)\b",
    "result": r"\b(result|outcome|as a result|reduced|increased|improved|saved|achieved|delivered|learned|resulting|which led)\b",
}
FILLER = re.compile(r"\b(um+|uh+|like,|you know|basically|kind of|sort of|i guess)\b", re.I)


def heuristic_score(question: dict, answer: str) -> dict:
    words = answer.split()
    n = len(words)
    low = answer.lower()
    notes, strengths, improve = [], [], []
    score = 0
    # length 0-25
    if n < 25:
        improve.append("Your answer is very short. Aim for 80-200 words with a concrete example.")
    elif n > 320:
        improve.append("This is long. Tighten it to the key points (about 2 minutes spoken).")
        score += 15
    else:
        strengths.append("Good length and level of detail.")
        score += 25
    if question.get("type") == "behavioral":
        hits = {k: bool(re.search(p, low)) for k, p in STAR.items()}
        score += 12 * sum(hits.values())
        missing = [k for k, v in hits.items() if not v]
        if missing:
            improve.append("Use the STAR structure - missing: " + ", ".join(missing) + ".")
        else:
            strengths.append("Clear STAR structure (situation, task, action, result).")
    else:
        sk = question.get("skill")
        covered = bool(sk and sk.lower() in low) or bool(extract_skills(answer))
        score += 20 if covered else 0
        (strengths if covered else improve).append("Mentions relevant technical terms." if covered else f"Name specific concepts/tools{f' for {sk}' if sk else ''} to show depth.")
        has_example = bool(re.search(r"\b(for example|for instance|e\.g\.|such as|in my project|i used)\b", low))
        score += 15 if has_example else 0
        (strengths if has_example else improve).append("Includes an example." if has_example else "Add a short real or concrete example.")
        score += 5
    if re.search(r"\d", answer):
        score += 10
        strengths.append("Uses specifics/numbers.")
    else:
        improve.append("Add a concrete number or measurable outcome where possible.")
    fillers = len(FILLER.findall(answer))
    if fillers > 3:
        improve.append("Reduce filler words (um, like, basically).")
        score -= 5
    return {"score": max(0, min(100, score + 15 if n >= 25 else score)), "strengths": strengths[:4], "improvements": improve[:4], "words": n}


def evaluate(question: dict, answer: str, role: str) -> dict:
    h = heuristic_score(question, answer)
    prompt = (
        f"Role: {role}\nInterview question: {question['text']}\n{ai.wrap_untrusted('candidate_answer', answer, 2500)}\n"
        'Give feedback as JSON: {"feedback":"2-3 sentences","stronger_answer":"a better version of the answer in under 120 words using ONLY facts the candidate gave"}.'
    )
    data = ai.ask_json([{"role": "user", "content": prompt}], system="You are a supportive, honest interview coach. " + ai.UNTRUSTED_NOTE, max_tokens=500)
    out = {**h, "engine": "rules", "feedback": " ".join(h["improvements"][:2]) or "Solid answer. Keep examples specific.", "stronger_answer": ""}
    if data and isinstance(data.get("feedback"), str):
        out.update(engine="ollama", feedback=data["feedback"][:800])
        if isinstance(data.get("stronger_answer"), str):
            out["stronger_answer"] = data["stronger_answer"][:900]
    return out


def summarize(session, answers) -> dict:
    if not answers:
        return {"average": 0, "answered": 0}
    avg = round(sum(a.score for a in answers) / len(answers))
    tips: dict[str, int] = {}
    for a in answers:
        for t in a.feedback.get("improvements", []):
            tips[t] = tips.get(t, 0) + 1
    top = [t for t, _ in sorted(tips.items(), key=lambda kv: -kv[1])[:3]]
    return {"average": avg, "answered": len(answers), "total": len(session.questions), "top_improvements": top,
            "verdict": "Interview-ready" if avg >= 75 else "Getting there" if avg >= 55 else "Needs more practice"}


_ = json
