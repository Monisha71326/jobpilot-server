import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.resumes import parser
from apps.resumes.models import Resume

from .base import RESUME_TEXT, APITestCase


class ParserUnitTests(APITestCase):
    def test_parse_fields(self):
        p = parser.parse_resume_text(RESUME_TEXT)
        self.assertEqual(p["email"], "asha.kumar@example.com")
        self.assertEqual(p["name"], "Asha Kumar")
        self.assertIn("linkedin", p["links"])
        for s in ("Python", "Django", "PostgreSQL", "Docker", "React", "TypeScript", "Redis", "REST APIs"):
            self.assertIn(s, p["skills"])
        for sec in ("summary", "experience", "education", "skills"):
            self.assertIn(sec, p["sections_found"])
        self.assertGreaterEqual(p["years_experience"], 5)  # 2020-present overlapping ranges are merged, not summed

    def test_year_ranges_union(self):
        from datetime import date

        self.assertEqual(parser.estimate_years("2018 - 2020, 2019 - 2021", today=date(2026, 1, 1)), 3.0)
        self.assertEqual(parser.estimate_years("2022 - Present", today=date(2026, 1, 1)), 4.0)
        self.assertEqual(parser.estimate_years("no dates"), 0.0)

    def test_skill_extraction_edge_cases(self):
        from apps.core.skills import extract_skills

        s = extract_skills("Experienced in C++, C#, Node.js and .NET. Used go to the store. No JavaScripture here. React Native apps.")
        self.assertIn("C++", s)
        self.assertIn("C#", s)
        self.assertIn("Node.js", s)
        self.assertIn(".NET", s)
        self.assertNotIn("Go", s)
        self.assertNotIn("JavaScript", s)
        self.assertIn("React Native", s)


class ResumeAPITests(APITestCase):
    def test_upload_docx_and_pdf(self):
        for kind in ("docx", "pdf"):
            r = self.upload_resume(kind=kind)
            self.assertEqual(r.status_code, 201, r.content)
            body = r.json()
            self.assertEqual(body["file_type"], kind)
            self.assertIn("Python", body["skills"])
            self.assertEqual(body["parsed_data"]["email"], "asha.kumar@example.com")
        self.assertEqual(Resume.objects.filter(user=self.user, is_primary=True).count(), 1)

    def test_rejects_bad_uploads(self):
        post = lambda name, data: self.client.post("/api/resumes/", {"file": SimpleUploadedFile(name, data)}, format="multipart")  # noqa: E731
        self.assertEqual(post("cv.exe", b"MZ....").status_code, 400)
        self.assertEqual(post("cv.pdf", b"not a pdf at all, just text" * 10).status_code, 400)
        self.assertEqual(post("cv.docx", b"not a zip" * 20).status_code, 400)
        self.assertEqual(post("cv.pdf", b"").status_code, 400)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("junk.txt", "x")
        self.assertEqual(post("cv.docx", buf.getvalue()).status_code, 400)  # zip but not a Word document
        self.assertEqual(self.client.post("/api/resumes/", {}, format="multipart").status_code, 400)

    def test_size_limit(self):
        from django.test import override_settings

        with override_settings(MAX_UPLOAD_MB=0):
            r = self.upload_resume()
        self.assertEqual(r.status_code, 400)
        self.assertIn("too large", r.json()["detail"])

    def test_stored_filename_is_server_generated(self):
        rid = self.upload_resume(name="../../evil name.docx").json()["id"]
        r = Resume.objects.get(pk=rid)
        self.assertNotIn("evil", r.file.name)
        self.assertTrue(r.file.name.startswith(f"resumes/{self.user.id}/"))

    def test_other_users_cannot_access(self):
        rid = self.upload_resume().json()["id"]
        _, other = self.make_user("other@example.com")
        for method, path in [("get", f"/api/resumes/{rid}/"), ("delete", f"/api/resumes/{rid}/"), ("get", f"/api/resumes/{rid}/file/"),
                             ("post", f"/api/resumes/{rid}/analyze/"), ("get", f"/api/resumes/{rid}/export/"), ("post", f"/api/resumes/{rid}/set-primary/")]:
            self.assertEqual(getattr(other, method)(path).status_code, 404, path)
        self.assertEqual(other.get("/api/resumes/").json(), [])

    def test_analyze_deterministic(self):
        rid = self.upload_resume().json()["id"]
        r = self.client.post(f"/api/resumes/{rid}/analyze/")
        self.assertEqual(r.status_code, 200, r.content)
        a = r.json()
        self.assertEqual(a["ai"]["engine"], "rules")
        self.assertGreaterEqual(a["analysis"]["score"], 60)
        ids = {c["id"]: c["passed"] for c in a["analysis"]["checks"]}
        self.assertTrue(ids["email"] and ids["metrics"] and ids["experience"])
        self.assertEqual(self.client.get(f"/api/resumes/{rid}/").json()["analysis_score"], a["analysis"]["score"])

    def test_analyze_against_job(self):
        from apps.jobs.models import Job, JobSource
        from django.utils import timezone

        rid = self.upload_resume().json()["id"]
        job = Job.objects.create(source=JobSource.objects.get(slug="demo"), external_id="t1", title="SRE", company="X", last_checked_at=timezone.now(),
                                 description="Kubernetes, Terraform, Docker and Python required")
        r = self.client.post(f"/api/resumes/{rid}/analyze/", {"job_id": job.id}, format="json").json()
        self.assertIn("Kubernetes", r["analysis"]["job_fit"]["missing_skills"])
        self.assertIn("Docker", r["analysis"]["job_fit"]["matched_skills"])

    def test_builder_versions_and_export(self):
        r = self.client.post("/api/resumes/builder/", {"title": "Built", "template": "modern"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        rid = r.json()["id"]
        content = {"basics": {"name": "Asha Kumar", "email": "a@example.com", "links": {"github": "https://github.com/a", "bad": "x"}},
                   "summary": "Dev", "skills": ["Python", "Python ", ""],
                   "experience": [{"company": "Acme", "title": "Engineer", "start": "2021", "end": "Present", "bullets": ["Built X", "Cut cost by 20%"]}]}
        v = self.client.post(f"/api/resumes/{rid}/versions/", {"content": content, "template": "compact", "note": "edit"}, format="json")
        self.assertEqual(v.status_code, 201, v.content)
        self.assertEqual(v.json()["version_no"], 2)
        self.assertNotIn("bad", v.json()["content"]["basics"]["links"])
        self.assertEqual(self.client.post(f"/api/resumes/{rid}/versions/", {"content": "oops"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/resumes/{rid}/versions/", {"content": content, "template": "nope"}, format="json").status_code, 400)
        self.assertEqual(len(self.client.get(f"/api/resumes/{rid}/versions/").json()), 2)
        e = self.client.get(f"/api/resumes/{rid}/export/")
        self.assertEqual(e.status_code, 200)
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(e.content)))
        self.assertIn(b"Cut cost by 20%", zipfile.ZipFile(io.BytesIO(e.content)).read("word/document.xml"))
        self.assertEqual(self.client.post(f"/api/resumes/{rid}/analyze/").status_code, 200)  # builder resumes can be analyzed too

    def test_primary_switching_and_delete(self):
        a = self.upload_resume().json()["id"]
        b = self.upload_resume().json()["id"]
        self.assertTrue(self.client.post(f"/api/resumes/{b}/set-primary/").json()["is_primary"])
        self.assertEqual(Resume.objects.filter(user=self.user, is_primary=True).count(), 1)
        self.assertEqual(self.client.delete(f"/api/resumes/{b}/").status_code, 204)
        self.assertTrue(Resume.objects.get(pk=a).is_primary)

    def test_to_builder_and_apply_to_profile(self):
        rid = self.upload_resume().json()["id"]
        v = self.client.post(f"/api/resumes/{rid}/to-builder/")
        self.assertEqual(v.status_code, 201)
        self.assertEqual(v.json()["content"]["basics"]["email"], "asha.kumar@example.com")
        r = self.client.post(f"/api/resumes/{rid}/apply-to-profile/").json()
        self.assertIn("Django", r["skills"])
