"""Skill taxonomy used for resume parsing, job matching and gap analysis (deterministic, no AI needed)."""
import re
from functools import lru_cache

# canonical name -> aliases (lowercase). Ambiguous single letters (C, R, Go) are deliberately handled via explicit aliases only.
TAXONOMY: dict[str, list[str]] = {
    "Python": ["python", "python3"],
    "JavaScript": ["javascript", "js", "ecmascript", "es6"],
    "TypeScript": ["typescript", "ts"],
    "Java": ["java"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "Go": ["golang", "go lang"],
    "Rust": ["rust"],
    "PHP": ["php"],
    "Ruby": ["ruby"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "R": ["r programming", "rstudio", "r language"],
    "SQL": ["sql", "t-sql", "pl/sql"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "React": ["react", "react.js", "reactjs"],
    "Next.js": ["next.js", "nextjs"],
    "Vue": ["vue", "vue.js", "vuejs"],
    "Angular": ["angular", "angularjs"],
    "Tailwind CSS": ["tailwind", "tailwindcss", "tailwind css"],
    "Redux": ["redux"],
    "Node.js": ["node.js", "nodejs", "node"],
    "Express.js": ["express.js", "expressjs"],
    "Django": ["django"],
    "Django REST Framework": ["drf", "django rest framework", "django-rest-framework"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring Boot": ["spring boot", "spring framework"],
    ".NET": [".net", "dotnet", "asp.net"],
    "Laravel": ["laravel"],
    "REST APIs": ["restful", "rest api", "rest apis", "restful api"],
    "GraphQL": ["graphql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "SQLite": ["sqlite"],
    "Elasticsearch": ["elasticsearch", "elastic search"],
    "Docker": ["docker", "docker compose", "docker-compose"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Linux": ["linux", "ubuntu", "bash", "shell scripting"],
    "Git": ["git", "github", "gitlab", "bitbucket"],
    "CI/CD": ["ci/cd", "cicd", "github actions", "jenkins", "gitlab ci"],
    "Terraform": ["terraform"],
    "Ansible": ["ansible"],
    "Nginx": ["nginx"],
    "Celery": ["celery"],
    "RabbitMQ": ["rabbitmq"],
    "Kafka": ["kafka", "apache kafka"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "neural networks"],
    "NLP": ["nlp", "natural language processing"],
    "Computer Vision": ["computer vision", "opencv"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow", "keras"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Data Analysis": ["data analysis", "data analytics", "analytics"],
    "Data Visualization": ["data visualization", "tableau", "power bi", "powerbi", "matplotlib"],
    "Excel": ["excel", "microsoft excel", "advanced excel"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Airflow": ["airflow", "apache airflow"],
    "LLMs": ["llm", "llms", "large language models", "generative ai", "genai", "langchain", "rag"],
    "Testing": ["unit testing", "pytest", "jest", "selenium", "cypress", "playwright", "test automation", "tdd"],
    "Agile": ["agile", "scrum", "kanban"],
    "Jira": ["jira"],
    "Figma": ["figma"],
    "UI/UX": ["ui/ux", "ux design", "ui design", "user experience", "wireframing"],
    "Microservices": ["microservices", "microservice"],
    "System Design": ["system design", "distributed systems"],
    "Data Structures": ["data structures", "algorithms", "dsa"],
    "OOP": ["oop", "object oriented", "object-oriented"],
    "Android": ["android"],
    "iOS": ["ios"],
    "React Native": ["react native"],
    "Flutter": ["flutter", "dart"],
    "Cybersecurity": ["cybersecurity", "cyber security", "infosec", "penetration testing"],
    "Networking": ["networking", "tcp/ip"],
    "DevOps": ["devops", "sre", "site reliability"],
    "Communication": ["communication", "presentation skills"],
    "Leadership": ["leadership", "team lead", "mentoring"],
    "Project Management": ["project management", "pmp", "stakeholder management"],
    "Product Management": ["product management", "product manager", "roadmapping"],
    "SEO": ["seo", "search engine optimization"],
    "Digital Marketing": ["digital marketing", "google ads", "social media marketing", "content marketing"],
    "Sales": ["sales", "lead generation", "b2b sales"],
    "Customer Support": ["customer support", "customer service", "helpdesk"],
    "Accounting": ["accounting", "tally", "gst", "bookkeeping", "financial reporting"],
    "Recruitment": ["recruitment", "talent acquisition", "sourcing"],
    "Content Writing": ["content writing", "copywriting", "technical writing"],
}

AMBIGUOUS_CANONICAL = {"Go", "R"}

# Which skills are generally "soft"; used to avoid overweighting them in match scores.
SOFT = {"Communication", "Leadership", "Agile", "Project Management"}

# Free, stable learning-resource roots. These point at official docs / well-known free courses only.
RESOURCES: dict[str, list[tuple[str, str]]] = {
    "Python": [("Official Python Tutorial", "https://docs.python.org/3/tutorial/")],
    "JavaScript": [("MDN JavaScript Guide", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide")],
    "TypeScript": [("TypeScript Handbook", "https://www.typescriptlang.org/docs/")],
    "React": [("React: Learn", "https://react.dev/learn")],
    "Django": [("Django Tutorial", "https://docs.djangoproject.com/en/stable/intro/tutorial01/")],
    "SQL": [("PostgreSQL Tutorial (official)", "https://www.postgresql.org/docs/current/tutorial.html")],
    "PostgreSQL": [("PostgreSQL Tutorial (official)", "https://www.postgresql.org/docs/current/tutorial.html")],
    "Git": [("Pro Git book", "https://git-scm.com/book/en/v2")],
    "Docker": [("Docker Get Started", "https://docs.docker.com/get-started/")],
    "HTML": [("MDN Learn Web Development", "https://developer.mozilla.org/en-US/docs/Learn")],
    "CSS": [("MDN Learn Web Development", "https://developer.mozilla.org/en-US/docs/Learn")],
    "Node.js": [("Node.js Learn", "https://nodejs.org/en/learn")],
    "Kubernetes": [("Kubernetes Tutorials", "https://kubernetes.io/docs/tutorials/")],
    "Machine Learning": [("Kaggle Learn", "https://www.kaggle.com/learn")],
    "Pandas": [("pandas Getting Started", "https://pandas.pydata.org/docs/getting_started/index.html")],
    "Go": [("A Tour of Go", "https://go.dev/tour/")],
    "Rust": [("The Rust Book", "https://doc.rust-lang.org/book/")],
    "Java": [("Dev.java Learn", "https://dev.java/learn/")],
    "Linux": [("Linux Journey", "https://linuxjourney.com/")],
    "Data Structures": [("CS50 (free, Harvard)", "https://cs50.harvard.edu/x/")],
}
GENERAL_RESOURCES = [
    ("roadmap.sh (free learning roadmaps)", "https://roadmap.sh"),
    ("freeCodeCamp (free curriculum)", "https://www.freecodecamp.org/learn"),
]


@lru_cache(maxsize=1)
def _alias_index() -> tuple[re.Pattern, dict[str, str]]:
    alias_to_canon: dict[str, str] = {}
    for canon, aliases in TAXONOMY.items():
        if canon not in AMBIGUOUS_CANONICAL:  # e.g. bare "go" / "r" are ordinary words; require explicit aliases
            alias_to_canon[canon.lower()] = canon
        for a in aliases:
            alias_to_canon.setdefault(a.lower(), canon)
    parts = sorted(alias_to_canon, key=len, reverse=True)
    pattern = re.compile(r"(?<![\w+#.])(" + "|".join(re.escape(p) for p in parts) + r")(?![\w+#]|\.\w)", re.IGNORECASE)
    return pattern, alias_to_canon


def extract_skills(text: str) -> list[str]:
    """Return canonical skill names found in text, ordered by first appearance."""
    if not text:
        return []
    pattern, mapping = _alias_index()
    seen: dict[str, None] = {}
    for m in pattern.finditer(text):
        canon = mapping.get(m.group(1).lower())
        if canon:
            seen.setdefault(canon, None)
    return list(seen)


def normalize_skill(name: str) -> str:
    _, mapping = _alias_index()
    return mapping.get(name.strip().lower(), name.strip())


def resources_for(skill: str) -> list[dict]:
    items = RESOURCES.get(skill, []) + GENERAL_RESOURCES
    return [{"title": t, "url": u} for t, u in items]
