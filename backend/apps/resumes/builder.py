"""Resume builder: structured content schema, templates, flattening, DOCX export."""
import io
import re

TEMPLATES = {
    "classic": {"label": "Classic", "description": "Serif, single column, ATS-friendly. Best for traditional industries."},
    "modern": {"label": "Modern", "description": "Clean sans-serif with accent headings. Good for tech and startups."},
    "compact": {"label": "Compact", "description": "Tight spacing to fit more on one page. Good for experienced candidates."},
}


def blank_content(user=None) -> dict:
    p = getattr(user, "profile", None)
    name = f"{user.first_name} {user.last_name}".strip() if user else ""
    return {
        "basics": {
            "name": name,
            "email": user.email if user else "",
            "phone": p.phone if p else "",
            "location": p.location if p else "",
            "headline": p.headline if p else "",
            "links": dict(p.links) if p and p.links else {},
        },
        "summary": p.summary if p else "",
        "experience": [],
        "education": [],
        "skills": list(p.skills) if p and p.skills else [],
        "projects": [],
        "certifications": [],
    }


def normalize_content(c: dict) -> dict:
    """Coerce arbitrary client JSON into the schema (and cap sizes). Raises ValueError on garbage."""
    if not isinstance(c, dict):
        raise ValueError("content must be an object")

    def s(v, n=300):
        return str(v or "").strip()[:n]

    def sl(v, n=60, m=80):
        return [s(x, m) for x in (v if isinstance(v, list) else []) if s(x, m)][:n]

    b = c.get("basics") if isinstance(c.get("basics"), dict) else {}
    links = b.get("links") if isinstance(b.get("links"), dict) else {}
    out = {
        "basics": {
            "name": s(b.get("name"), 80), "email": s(b.get("email"), 120), "phone": s(b.get("phone"), 30),
            "location": s(b.get("location"), 100), "headline": s(b.get("headline"), 120),
            "links": {k: s(v, 200) for k, v in links.items() if k in {"linkedin", "github", "portfolio", "website"} and s(v, 200)},
        },
        "summary": s(c.get("summary"), 1200),
        "experience": [], "education": [], "projects": [],
        "skills": sl(c.get("skills")),
        "certifications": sl(c.get("certifications"), 20, 160),
    }
    for e in (c.get("experience") if isinstance(c.get("experience"), list) else [])[:20]:
        if isinstance(e, dict):
            out["experience"].append({
                "company": s(e.get("company"), 120), "title": s(e.get("title"), 120), "location": s(e.get("location"), 100),
                "start": s(e.get("start"), 20), "end": s(e.get("end"), 20), "bullets": sl(e.get("bullets"), 12, 400),
            })
    for e in (c.get("education") if isinstance(c.get("education"), list) else [])[:10]:
        if isinstance(e, dict):
            out["education"].append({
                "school": s(e.get("school"), 140), "degree": s(e.get("degree"), 140),
                "start": s(e.get("start"), 20), "end": s(e.get("end"), 20), "details": s(e.get("details"), 300),
            })
    for e in (c.get("projects") if isinstance(c.get("projects"), list) else [])[:12]:
        if isinstance(e, dict):
            out["projects"].append({"name": s(e.get("name"), 120), "description": s(e.get("description"), 400), "bullets": sl(e.get("bullets"), 8, 300)})
    return out


def flatten_content(c: dict) -> str:
    b = c.get("basics", {})
    lines = [b.get("name", ""), b.get("headline", ""), b.get("email", ""), b.get("phone", ""), b.get("location", ""), "", c.get("summary", ""), ""]
    lines.append("EXPERIENCE")
    for e in c.get("experience", []):
        lines.append(f"{e.get('title')} - {e.get('company')} ({e.get('start')} - {e.get('end')})")
        lines += [f"- {x}" for x in e.get("bullets", [])]
    lines.append("EDUCATION")
    for e in c.get("education", []):
        lines.append(f"{e.get('degree')} - {e.get('school')} ({e.get('start')} - {e.get('end')}) {e.get('details', '')}")
    lines.append("SKILLS")
    lines.append(", ".join(c.get("skills", [])))
    lines.append("PROJECTS")
    for p in c.get("projects", []):
        lines.append(f"{p.get('name')}: {p.get('description')}")
        lines += [f"- {x}" for x in p.get("bullets", [])]
    if c.get("certifications"):
        lines.append("CERTIFICATIONS")
        lines += c["certifications"]
    return "\n".join(l for l in lines if l is not None)


def from_parsed(parsed: dict, user=None) -> dict:
    """Best-effort conversion of a parsed upload into editable builder content. User should review it."""
    c = blank_content(user)
    b = c["basics"]
    b["name"] = parsed.get("name") or b["name"]
    b["email"] = parsed.get("email") or b["email"]
    b["phone"] = parsed.get("phone") or b["phone"]
    b["links"].update(parsed.get("links", {}))
    secs = parsed.get("section_text", {})
    c["summary"] = (secs.get("summary") or c["summary"])[:1200]
    c["skills"] = list(dict.fromkeys(parsed.get("skills", []) + c["skills"]))[:40]
    if secs.get("experience"):
        bullets = [re.sub(r"^\s*[-•*▪●◦]\s+", "", l).strip() for l in secs["experience"].split("\n") if re.match(r"^\s*[-•*▪●◦]\s+\S", l)]
        c["experience"] = [{"company": "", "title": "Imported experience", "location": "", "start": "", "end": "", "bullets": bullets[:12] or [secs["experience"][:400]]}]
    if secs.get("education"):
        c["education"] = [{"school": "", "degree": secs["education"].split("\n")[0][:140], "start": "", "end": "", "details": secs["education"][:300]}]
    return c


# ---------------------------------------------------------------- DOCX export
_STYLE = {
    "classic": {"font": "Times New Roman", "size": 11, "accent": (0, 0, 0), "margin": 0.9, "center": True},
    "modern": {"font": "Calibri", "size": 10.5, "accent": (37, 99, 235), "margin": 0.8, "center": False},
    "compact": {"font": "Arial", "size": 9.5, "accent": (31, 41, 55), "margin": 0.55, "center": False},
}


def export_docx(content: dict, template: str = "classic") -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor

    st = _STYLE.get(template, _STYLE["classic"])
    doc = Document()
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Inches(st["margin"])
        sec.top_margin = sec.bottom_margin = Inches(st["margin"])
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = st["font"], Pt(st["size"])
    normal.paragraph_format.space_after = Pt(2)
    accent = RGBColor(*st["accent"])

    def heading(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        r = p.add_run(text.upper())
        r.bold, r.font.size, r.font.color.rgb = True, Pt(st["size"] + 1), accent
        return p

    b = content.get("basics", {})
    p = doc.add_paragraph()
    if st["center"]:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(b.get("name") or "Your Name")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(st["size"] + 9), accent
    if b.get("headline"):
        hp = doc.add_paragraph(b["headline"])
        hp.alignment = p.alignment
    contact = " | ".join(x for x in [b.get("email"), b.get("phone"), b.get("location"), *b.get("links", {}).values()] if x)
    if contact:
        cp = doc.add_paragraph(contact)
        cp.alignment = p.alignment
    if content.get("summary"):
        heading("Summary")
        doc.add_paragraph(content["summary"])
    if content.get("experience"):
        heading("Experience")
        for e in content["experience"]:
            hp = doc.add_paragraph()
            hp.paragraph_format.space_before = Pt(4)
            hp.add_run(e.get("title", "")).bold = True
            hp.add_run(f"  {e.get('company', '')}" + (f", {e['location']}" if e.get("location") else ""))
            dates = " - ".join(x for x in [e.get("start"), e.get("end")] if x)
            if dates:
                hp.add_run(f"   ({dates})").italic = True
            for bl in e.get("bullets", []):
                doc.add_paragraph(bl, style="List Bullet")
    if content.get("projects"):
        heading("Projects")
        for pr in content["projects"]:
            pp = doc.add_paragraph()
            pp.add_run(pr.get("name", "")).bold = True
            if pr.get("description"):
                pp.add_run(f" - {pr['description']}")
            for bl in pr.get("bullets", []):
                doc.add_paragraph(bl, style="List Bullet")
    if content.get("education"):
        heading("Education")
        for e in content["education"]:
            ep = doc.add_paragraph()
            ep.add_run(e.get("degree", "")).bold = True
            ep.add_run(f"  {e.get('school', '')}")
            dates = " - ".join(x for x in [e.get("start"), e.get("end")] if x)
            if dates:
                ep.add_run(f"   ({dates})").italic = True
            if e.get("details"):
                doc.add_paragraph(e["details"])
    if content.get("skills"):
        heading("Skills")
        doc.add_paragraph(", ".join(content["skills"]))
    if content.get("certifications"):
        heading("Certifications")
        for c in content["certifications"]:
            doc.add_paragraph(c, style="List Bullet")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
