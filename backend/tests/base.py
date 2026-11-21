import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.core import ai
from apps.jobs import ingest

User = get_user_model()
_TMP_MEDIA = tempfile.mkdtemp(prefix="jobpilot-test-media-")

RESUME_TEXT = """Asha Kumar
asha.kumar@example.com | +91 98765 43210 | Chennai, India
linkedin.com/in/ashakumar github.com/ashakumar

SUMMARY
Backend developer focused on Python and Django APIs.

EXPERIENCE
Software Engineer, Acme Tech (2021 - Present)
- Built REST APIs with Django REST Framework and PostgreSQL serving 50000 users
- Reduced API latency by 40% by adding Redis caching
- Led migration to Docker and CI/CD with GitHub Actions, cutting deploy time from 30 minutes to 5
- Wrote pytest suites and mentored two junior developers
Intern, Beta Labs (2020 - 2021)
- Developed React dashboards using TypeScript and Tailwind CSS

EDUCATION
B.E. Computer Science, Anna University (2016 - 2020)

SKILLS
Python, Django, PostgreSQL, Docker, Git, SQL, Redis, React, TypeScript, REST APIs, Linux
"""


def make_docx(text: str = RESUME_TEXT) -> bytes:
    import docx

    d = docx.Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def make_pdf(text: str = RESUME_TEXT) -> bytes:
    """Hand-built single-page text PDF (no extra dependency)."""
    lines = [l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for l in text.split("\n")]
    content = "BT /F1 10 Tf 40 780 Td 12 TL\n" + "\n".join(f"({l}) Tj T*" for l in lines) + "\nET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return out.encode("latin-1")


@override_settings(OLLAMA_ENABLED=False, MEDIA_ROOT=_TMP_MEDIA, JOB_SOURCES_ENABLED=True)
class APITestCase(TestCase):
    password = "S3cure-pass-phrase!"

    def setUp(self):
        ai._status_cache.update(at=0.0, value=None)
        ingest.ensure_sources()
        self.user, self.client = self.make_user("asha@example.com")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)

    def make_user(self, email, **extra):
        u = User.objects.create_user(username=email, email=email, password=self.password, first_name=extra.get("first_name", "Asha"), last_name="Kumar")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=u).key}")
        return u, c

    def upload_resume(self, client=None, kind="docx", name=None):
        client = client or self.client
        data = make_docx() if kind == "docx" else make_pdf()
        f = SimpleUploadedFile(name or f"resume.{kind}", data)
        return client.post("/api/resumes/", {"file": f}, format="multipart")
