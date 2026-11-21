"""Resume file validation + text extraction + structured parsing. Pure Python, no AI required."""
import io
import re
from datetime import date

from django.conf import settings

from apps.core.skills import extract_skills

ALLOWED = {".pdf": "pdf", ".docx": "docx"}


class ResumeError(ValueError):
    pass


def validate_upload(upload) -> str:
    """Check extension, size and magic bytes. Returns file_type ('pdf' | 'docx')."""
    name = (upload.name or "").lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED:
        raise ResumeError("Only PDF and DOCX files are supported.")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if upload.size > max_bytes:
        raise ResumeError(f"File is too large (max {settings.MAX_UPLOAD_MB} MB).")
    if upload.size == 0:
        raise ResumeError("File is empty.")
    head = upload.read(8)
    upload.seek(0)
    if ALLOWED[ext] == "pdf" and not head.startswith(b"%PDF"):
        raise ResumeError("This file does not look like a real PDF.")
    if ALLOWED[ext] == "docx" and not head.startswith(b"PK\x03\x04"):
        raise ResumeError("This file does not look like a real DOCX.")
    return ALLOWED[ext]


def extract_text(data: bytes, file_type: str) -> tuple[str, int, dict]:
    """Return (text, page_count, extra) where extra has e.g. docx table count."""
    if file_type == "pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ResumeError("Password-protected PDFs are not supported.")
            pages = reader.pages[:15]
            text = "\n".join((p.extract_text() or "") for p in pages)
            return _tidy(text), len(reader.pages), {}
        except ResumeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ResumeError("Could not read this PDF. Try exporting it again.") from exc
    if file_type == "docx":
        import docx

        try:
            d = docx.Document(io.BytesIO(data))
        except Exception as exc:  # noqa: BLE001
            raise ResumeError("Could not read this DOCX file.") from exc
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return _tidy("\n".join(parts)), 0, {"tables": len(d.tables)}
    raise ResumeError("Unsupported file type.")


def _tidy(text: str) -> str:
    text = text.replace("\x00", "").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


SECTION_HEADS = {
    "summary": r"summary|objective|profile|about me|career objective|professional summary",
    "experience": r"work experience|professional experience|experience|employment( history)?|work history|internships?",
    "education": r"education|academic(s| background| qualifications)?|qualifications",
    "skills": r"(technical |key |core )?skills|technologies|tech stack|competencies",
    "projects": r"projects|personal projects|academic projects",
    "certifications": r"certifications?|licenses|courses|training",
    "achievements": r"achievements|awards|honors|accomplishments",
}
_HEAD_RE = {k: re.compile(rf"^\s*(?:{v})\s*:?\s*$", re.I) for k, v in SECTION_HEADS.items()}

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3,5}\)?[\s-]?)\d{3,5}[\s-]?\d{3,5}(?!\d)")
LINKEDIN = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9_%-]+/?", re.I)
GITHUB = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+/?", re.I)

MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_RANGE = re.compile(
    rf"(?:(?:{MONTHS})[a-z]*\.?\s+)?((?:19|20)\d{{2}})\s*(?:-|–|—|to)\s*(?:(?:(?:{MONTHS})[a-z]*\.?\s+)?((?:19|20)\d{{2}})|(present|current|now|till date|ongoing))",
    re.I,
)


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.split("\n"):
        stripped = line.strip()
        matched = None
        if 0 < len(stripped) <= 40:
            for key, rx in _HEAD_RE.items():
                if rx.match(stripped):
                    matched = key
                    break
        if matched:
            current = matched
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip() or k == "header"}


def estimate_years(text: str, today: date | None = None) -> float:
    """Union of year ranges like '2019 - 2022' or '2021 - Present', in years (rounded to 0.5)."""
    today = today or date.today()
    spans = []
    for m in _RANGE.finditer(text):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else today.year
        if 1980 <= start <= end <= today.year + 1:
            spans.append((start, max(end, start)))
    if not spans:
        return 0.0
    spans.sort()
    total, (cs, ce) = 0, spans[0]
    for s, e in spans[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            total += ce - cs
            cs, ce = s, e
    total += ce - cs
    return min(round(total * 2) / 2, 50.0)


def guess_name(header: str) -> str:
    for line in header.split("\n")[:6]:
        line = line.strip()
        if not line or "@" in line or any(c.isdigit() for c in line) or len(line) > 50:
            continue
        words = line.split()
        if 1 < len(words) <= 4 and all(w[:1].isalpha() for w in words):
            return line.title() if line.isupper() else line
    return ""


def parse_resume_text(text: str) -> dict:
    sections = split_sections(text)
    header = sections.get("header", "")
    email = EMAIL.search(text)
    phone = next((m.group(0).strip() for m in PHONE.finditer(header + "\n" + text[:600]) if len(re.sub(r"\D", "", m.group(0))) >= 10), "")
    linkedin = LINKEDIN.search(text)
    github = GITHUB.search(text)
    exp_text = sections.get("experience", "") or text
    bullets = [l for l in text.split("\n") if re.match(r"^\s*[-•*▪●◦]\s+\S", l)]
    return {
        "name": guess_name(header),
        "email": email.group(0) if email else "",
        "phone": phone,
        "links": {k: v.group(0) for k, v in (("linkedin", linkedin), ("github", github)) if v},
        "sections_found": [k for k in sections if k != "header"],
        "skills": extract_skills(text),
        "years_experience": estimate_years(exp_text),
        "bullet_count": len(bullets),
        "word_count": len(text.split()),
        "section_text": {k: v[:4000] for k, v in sections.items() if k != "header"},
    }
