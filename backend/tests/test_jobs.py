from unittest import mock

from django.utils import timezone

from apps.jobs import matching
from apps.jobs.adapters import base
from apps.jobs.models import Job, JobSource

from .base import APITestCase

REMOTIVE = {"jobs": [
    {"id": 101, "url": "https://remotive.com/remote-jobs/software-dev/python-dev-101", "title": "Senior Python Developer", "company_name": "Acme",
     "job_type": "full_time", "publication_date": "2026-10-20T10:00:00", "candidate_required_location": "Worldwide", "salary": "",
     "description": "<p>We need 5+ years of <b>Python</b>, Django, PostgreSQL and Docker.</p><script>alert(1)</script>"},
    {"id": 102, "url": "https://remotive.com/remote-jobs/x-102", "title": "Frontend Engineer", "company_name": "Beta",
     "job_type": "contract", "publication_date": "2026-10-21T10:00:00", "candidate_required_location": "USA only",
     "description": "<p>React and TypeScript, 2-4 years.</p>"},
]}
GREENHOUSE = {"jobs": [{"id": 1, "title": "Backend Engineer", "updated_at": "2026-10-01T10:00:00-04:00", "location": {"name": "Remote - India"},
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1", "content": "&lt;p&gt;Python and SQL&lt;/p&gt;"},
                       {"id": 2, "title": "Designer", "updated_at": "2026-10-01T10:00:00-04:00", "location": {"name": "NYC"},
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/2", "content": "&lt;p&gt;Figma&lt;/p&gt;"}]}


def mk_job(title="Python Developer", company="Acme", desc="Python Django PostgreSQL REST APIs Docker. 2+ years.", **kw):
    return Job.objects.create(
        source=kw.pop("source", None) or JobSource.objects.get(slug="demo"), external_id=kw.pop("external_id", f"{title}-{company}"),
        title=title, company=company, description=desc, last_checked_at=timezone.now(), skills=kw.pop("skills", []), **kw)


class SSRFTests(APITestCase):
    def test_blocks_private_and_non_http(self):
        for url in ["http://127.0.0.1/", "http://localhost:8000/admin", "http://10.0.0.5/", "http://169.254.169.254/latest/meta-data/",
                    "http://192.168.1.1/", "http://[::1]/", "file:///etc/passwd", "ftp://example.com/x", "http://0.0.0.0/"]:
            with self.assertRaises(base.FetchError, msg=url):
                base.assert_public_url(url)

    def test_redirect_to_private_is_blocked(self):
        class Resp:
            is_redirect, status_code, headers = True, 302, {"Location": "http://169.254.169.254/"}

        calls = []

        def resolver(host, *a, **k):
            calls.append(host)
            return [(2, 1, 6, "", ("93.184.216.34" if host == "jobs.example.com" else "169.254.169.254", 0))]

        with mock.patch.object(base, "robots_allows", return_value=True), mock.patch("socket.getaddrinfo", side_effect=resolver), \
                mock.patch.object(base.requests, "get", return_value=Resp()):
            with self.assertRaises(base.FetchError):
                base.fetch_public_page("https://jobs.example.com/p/1")
        self.assertIn("169.254.169.254", calls)  # the redirect hop was re-validated

    def test_import_endpoint_reports_block_without_bypass(self):
        with mock.patch("apps.jobs.adapters.user_provided.fetch_public_page", side_effect=base.FetchError("The site blocked automated access (HTTP 403). Please paste the job description instead.")):
            r = self.client.post("/api/jobs/import/", {"url": "https://example.com/job/1"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.json()["needs_paste"])


class AdapterTests(APITestCase):
    def test_remotive_refresh_stores_attribution_and_respects_interval(self):
        with mock.patch("apps.jobs.adapters.sources.http_json", return_value=REMOTIVE) as m:
            r = self.client.post("/api/jobs/sources/remotive/refresh/", {"query": "python"}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual((r.json()["created"], r.json()["fetched"]), (2, 2))
            self.assertIn("Remotive", r.json()["attribution"])
            r2 = self.client.post("/api/jobs/sources/remotive/refresh/", {}, format="json")
            self.assertTrue(r2.json()["skipped"])  # Remotive asks for <= 4 fetches/day: we enforce a 6h floor
            self.assertEqual(m.call_count, 1)
        j = Job.objects.get(external_id="101")
        self.assertNotIn("alert(1)", j.description)  # scripts stripped
        self.assertEqual(j.min_experience, 5)
        self.assertIn("Django", j.skills)
        self.assertTrue(j.is_remote)
        self.assertIsNotNone(j.last_checked_at)
        src = self.client.get("/api/jobs/sources/").json()["sources"]
        self.assertTrue(next(s for s in src if s["slug"] == "remotive")["next_allowed_at"])

    def test_refresh_disabled_and_unknown(self):
        with self.settings(JOB_SOURCES_ENABLED=False):
            self.assertEqual(self.client.post("/api/jobs/sources/remotive/refresh/", {}, format="json").status_code, 503)
        self.assertEqual(self.client.post("/api/jobs/sources/linkedin/refresh/", {}, format="json").status_code, 404)

    def test_adapter_failure_is_reported_not_fabricated(self):
        with mock.patch("apps.jobs.adapters.sources.http_json", side_effect=base.FetchError("Could not reach remotive.com: ConnectionError")):
            r = self.client.post("/api/jobs/sources/remotive/refresh/", {}, format="json")
        self.assertEqual(r.status_code, 502)
        self.assertEqual(Job.objects.filter(source__slug="remotive").count(), 0)

    def test_greenhouse_board_token_and_deactivation(self):
        self.assertEqual(self.client.post("/api/jobs/sources/greenhouse/refresh/", {"token": "../../etc"}, format="json").status_code, 400)
        with mock.patch("apps.jobs.adapters.sources.http_json", return_value=GREENHOUSE):
            r = self.client.post("/api/jobs/sources/greenhouse/refresh/", {"token": "acme"}, format="json")
        self.assertEqual(r.json()["created"], 2)
        self.assertTrue(Job.objects.get(external_id="acme:1").is_remote)
        from apps.jobs.models import TrackedBoard

        TrackedBoard.objects.update(last_fetched_at=None)
        with mock.patch("apps.jobs.adapters.sources.http_json", return_value={"jobs": GREENHOUSE["jobs"][:1]}):
            r = self.client.post("/api/jobs/sources/greenhouse/refresh/", {"token": "acme"}, format="json")
        self.assertEqual(r.json()["deactivated"], 1)
        self.assertFalse(Job.objects.get(external_id="acme:2").is_active)
        listed = self.client.get("/api/jobs/").json()
        self.assertEqual([j["title"] for j in listed["results"]], ["Backend Engineer"])


class ImportTests(APITestCase):
    def test_import_text_dedup_and_privacy(self):
        text = "Python Developer at Zeta\nWe need Python, Django and SQL. 2+ years of experience. Remote friendly."
        r = self.client.post("/api/jobs/import/", {"text": text, "company": "Zeta"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        jid = r.json()["id"]
        self.assertEqual(r.json()["source"]["kind"], "user")
        self.assertEqual(self.client.post("/api/jobs/import/", {"text": text, "company": "Zeta"}, format="json").status_code, 200)  # duplicate -> same job
        self.assertEqual(Job.objects.filter(added_by=self.user).count(), 1)
        _, other = self.make_user("b@example.com")
        self.assertEqual(other.get(f"/api/jobs/{jid}/").status_code, 404)
        self.assertEqual(other.get("/api/jobs/").json()["count"], 0)
        self.assertEqual(other.delete(f"/api/jobs/{jid}/").status_code, 404)
        self.assertEqual(other.post("/api/saved-jobs/", {"job_id": jid}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/jobs/{jid}/").status_code, 204)

    def test_import_from_url_parses_jsonld(self):
        html = '''<html><head><title>x</title><script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting",
        "title":"Data Analyst","hiringOrganization":{"@type":"Organization","name":"Gamma"},"description":"<p>SQL, Excel and Tableau. 1-3 years.</p>",
        "jobLocationType":"TELECOMMUTE","datePosted":"2026-10-10","jobLocation":{"address":{"addressLocality":"Pune","addressCountry":"IN"}}}</script></head><body></body></html>'''
        with mock.patch("apps.jobs.adapters.user_provided.fetch_public_page", return_value=html):
            r = self.client.post("/api/jobs/import/", {"url": "https://careers.gamma.example/jobs/9"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        j = r.json()
        self.assertEqual((j["title"], j["company"], j["is_remote"]), ("Data Analyst", "Gamma", True))
        self.assertEqual(j["apply_url"], "https://careers.gamma.example/jobs/9")  # links back to the original page
        self.assertEqual((j["min_experience"], j["max_experience"]), (1, 3))

    def test_import_requires_input(self):
        self.assertEqual(self.client.post("/api/jobs/import/", {}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/jobs/import/", {"text": "too short"}, format="json").status_code, 400)


class SearchTests(APITestCase):
    def setUp(self):
        super().setUp()
        mk_job("Python Developer", "Acme", "Python Django PostgreSQL. 2+ years.", location="Chennai, India", skills=["Python", "Django", "PostgreSQL"], min_experience=2)
        mk_job("Remote React Engineer", "Beta", "React TypeScript Tailwind CSS", location="Remote", is_remote=True, skills=["React", "TypeScript"])
        mk_job("Staff Platform Engineer", "Gamma", "Kubernetes Terraform AWS. 8+ years.", location="Pune", skills=["Kubernetes", "Terraform", "AWS"], min_experience=8)
        mk_job("Hidden", "Zed", "Old", is_active=False)

    def titles(self, **params):
        return [j["title"] for j in self.client.get("/api/jobs/", params).json()["results"]]

    def test_filters(self):
        self.assertEqual(len(self.titles()), 3)
        self.assertEqual(self.titles(q="python"), ["Python Developer"])
        self.assertEqual(self.titles(remote="true"), ["Remote React Engineer"])
        self.assertEqual(self.titles(skills="React,TypeScript"), ["Remote React Engineer"])
        self.assertEqual(self.titles(skills="React,Django"), [])
        self.assertEqual(self.titles(location="chennai"), ["Python Developer"])
        self.assertEqual(sorted(self.titles(experience="3")), ["Python Developer", "Remote React Engineer"])
        self.assertEqual(self.titles(q="python django"), ["Python Developer"])
        self.assertEqual(self.titles(q="'; DROP TABLE jobs_job; --"), [])
        self.assertEqual(len(self.titles(source="demo")), 3)

    def test_save_and_filter_saved(self):
        jid = Job.objects.get(title="Python Developer").id
        self.assertEqual(self.client.post("/api/saved-jobs/", {"job_id": jid}, format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/saved-jobs/", {"job_id": jid}, format="json").status_code, 200)  # idempotent
        self.assertEqual(self.titles(saved="true"), ["Python Developer"])
        self.assertTrue(self.client.get("/api/jobs/").json()["results"][0]["is_saved"] in (True, False))
        self.assertEqual(self.client.patch(f"/api/saved-jobs/{jid}/", {"note": "great"}, format="json").json()["note"], "great")
        self.assertEqual(self.client.get("/api/saved-jobs/").json()[0]["note"], "great")
        self.assertEqual(self.client.delete(f"/api/saved-jobs/{jid}/").status_code, 204)
        self.assertEqual(self.titles(saved="true"), [])

    def test_match_sort_and_explanation(self):
        self.upload_resume()
        self.client.patch("/api/profile/", {"years_experience": 4, "desired_roles": ["Backend Developer"], "desired_locations": ["Chennai"]}, format="json")
        res = self.client.get("/api/jobs/", {"sort": "match"}).json()
        self.assertTrue(res["has_resume"])
        scores = [j["match_score"] for j in res["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(res["results"][0]["title"], "Python Developer")
        self.assertEqual(res["results"][-1]["title"], "Staff Platform Engineer")
        d = self.client.get(f"/api/jobs/{res['results'][0]['id']}/").json()["match"]
        self.assertAlmostEqual(sum(f["score"] for f in d["factors"]), d["score"], delta=1.5)
        self.assertEqual({f["factor"] for f in d["factors"]}, {"Skills", "Role fit", "Resume relevance", "Experience", "Location & remote"})
        self.assertIn("Python", d["matched_skills"])
        worst = self.client.get(f"/api/jobs/{res['results'][-1]['id']}/").json()["match"]
        self.assertIn("Kubernetes", worst["missing_skills"])
        self.assertTrue(worst["eligibility"]["warnings"])  # experience gap flagged
        self.assertLess(worst["score"], d["score"])

    def test_match_recomputed_when_profile_changes(self):
        self.upload_resume()
        jid = Job.objects.get(title="Remote React Engineer").id
        before = self.client.get(f"/api/jobs/{jid}/").json()["match"]["score"]
        self.client.patch("/api/profile/", {"remote_preference": "onsite"}, format="json")
        mk = self.client.get(f"/api/jobs/{jid}/").json()["match"]
        self.assertTrue(any("Location" in f["factor"] for f in mk["factors"]))
        self.assertLess(mk["score"], before)

    def test_matching_unit_neutral_when_no_skills(self):
        self.upload_resume()
        from apps.resumes.models import Resume

        ctx = matching.candidate_context(self.user, Resume.objects.get(user=self.user))
        j = Job(title="Office Assistant", company="X", description="Answer phones.", location="", skills=[])
        out = matching.score_job(ctx, j)
        self.assertTrue(any("neutral" in f["detail"] for f in out["factors"] if f["factor"] == "Skills"))
        self.assertGreaterEqual(out["score"], 0)
        self.assertLessEqual(out["score"], 100)


class DemoDataTests(APITestCase):
    def test_demo_jobs_are_labelled_and_have_no_apply_url(self):
        from django.core.management import call_command

        call_command("load_demo_jobs", verbosity=0)
        call_command("load_demo_jobs", verbosity=0)  # idempotent
        jobs = Job.objects.filter(source__slug="demo")
        self.assertEqual(jobs.count(), 8)
        self.assertTrue(all(j.title.startswith("[DEMO]") and not j.apply_url and "fictional" in j.company for j in jobs))
