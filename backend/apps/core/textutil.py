"""Small dependency-free text helpers (tokenizing, cosine similarity, experience extraction)."""
import math
import re
from collections import Counter

STOPWORDS = set(
    """a an the and or but if then else of to in on at by for with from as is are was were be been being this that these those it its
    we you they he she i our your their his her my me us them will would can could should may might must do does did done have has had
    not no yes so than too very just also into over under about across per via etc using use used work working team teams role
    responsible responsibilities required requirements preferred ability strong good great experience years year plus including include
    looking join company candidate position job""".split()
)

_WORD = re.compile(r"[a-z][a-z0-9+#.]{1,}")


def tokens(text: str) -> list[str]:
    return [t.strip(".") for t in _WORD.findall((text or "").lower()) if t.strip(".") not in STOPWORDS and len(t.strip(".")) > 1]


def cosine(a_text: str, b_text: str) -> float:
    """Sublinear-TF cosine similarity in [0, 1]."""
    a, b = Counter(tokens(a_text)), Counter(tokens(b_text))
    if not a or not b:
        return 0.0
    va = {t: 1 + math.log(c) for t, c in a.items()}
    vb = {t: 1 + math.log(c) for t, c in b.items()}
    dot = sum(va[t] * vb[t] for t in va.keys() & vb.keys())
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    return dot / (na * nb) if na and nb else 0.0


def vec_cosine(u: list[float], v: list[float]) -> float:
    dot = sum(x * y for x, y in zip(u, v))
    nu, nv = math.sqrt(sum(x * x for x in u)), math.sqrt(sum(y * y for y in v))
    return dot / (nu * nv) if nu and nv else 0.0


_RANGE = re.compile(r"(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*\+?\s*(?:years|yrs)", re.I)
_MIN = re.compile(r"(\d{1,2})\s*\+?\s*(?:years|yrs)", re.I)


def extract_experience_range(text: str) -> tuple[int | None, int | None]:
    """Find 'N+ years' / 'N-M years' requirements in job text. Returns (min, max) or (None, None)."""
    if not text:
        return None, None
    m = _RANGE.search(text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return min(lo, hi), max(lo, hi)
    m = _MIN.search(text)
    if m:
        n = int(m.group(1))
        return (n, None) if n <= 25 else (None, None)
    if re.search(r"\b(fresher|entry[- ]level|graduate|intern(ship)?)\b", text, re.I):
        return 0, 1
    return None, None


def clean_html(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()
