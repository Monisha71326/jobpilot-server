from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications.models import Application, Reminder

from .base import APITestCase
from .test_jobs import mk_job


class ApplicationFlowTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.upload_resume()
        self.client.patch("/api/profile/", {"phone": "+91 99999 11111", "location": "Chennai, India", "years_experience": 4,
                                            "links": {"linkedin": "https://linkedin.com/in/asha"}}, format="json")
        self.job = mk_job("Python Developer", "Acme", "Python Django PostgreSQL. 2+ years.", location="Chennai", apply_url="https://acme.example/apply/1")

    def create(self, **kw):
        return self.client.post("/api/applications/", {"job_id": self.job.id, **kw}, format="json")

    def test_create_selects_resume_and_blocks_duplicates(self):
        r = self.create()
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual((body["status"], body["job_title"], body["company"]), ("wishlist", "Python Developer", "Acme"))
        self.assertIsNotNone(body["resume_id"])
        self.assertTrue(body["match_score"] > 0)
        again = self.create()
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["code"], "duplicate")
        self.assertFalse(again.json()["can_force"])
        self.assertEqual(Application.objects.filter(user=self.user).count(), 1)

    def test_cross_source_duplicate_detected_but_can_be_forced(self):
        self.create()
        twin = mk_job("Python Developer", "ACME ", "Same posting on another board", location="chennai", external_id="other-board-1")
        r = self.client.post("/api/applications/", {"job_id": twin.id}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.json()["can_force"])
        self.assertEqual(self.client.post("/api/applications/", {"job_id": twin.id, "force": True}, format="json").status_code, 201)

    def test_manual_application_and_validation(self):
        r = self.client.post("/api/applications/", {"job_title": "Analyst", "company": "Delta", "apply_url": "javascript:alert(1)"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/applications/", {"job_title": "Analyst", "company": "Delta", "apply_url": "https://delta.example/j"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.post("/api/applications/", {"job_title": "", "company": "Delta"}, format="json").status_code, 400)

    def test_applied_requires_explicit_confirmation(self):
        aid = self.create().json()["id"]
        r = self.client.post(f"/api/applications/{aid}/move/", {"status": "applied"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "needs_confirmation")
        r = self.client.patch(f"/api/applications/{aid}/", {"status": "applied"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Application.objects.get(pk=aid).status, "wishlist")
        r = self.client.post(f"/api/applications/{aid}/move/", {"status": "applied", "confirm_submitted": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        a = Application.objects.get(pk=aid)
        self.assertEqual(a.status, "applied")
        self.assertIsNotNone(a.applied_at)
        self.assertIsNotNone(a.submission_confirmed_at)
        self.assertTrue(Reminder.objects.filter(application=a, title__startswith="Follow up").exists())
        kinds = list(a.activities.values_list("kind", flat=True))
        self.assertIn("submitted", kinds)

    def test_database_refuses_unconfirmed_applied(self):
        a = Application.objects.create(user=self.user, job_title="X", company="Y")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Application.objects.filter(pk=a.pk).update(status="applied")

    def test_kanban_reorder_and_status_validation(self):
        ids = [self.client.post("/api/applications/", {"job_title": f"T{i}", "company": "C"}, format="json").json()["id"] for i in range(3)]
        r = self.client.post(f"/api/applications/{ids[0]}/move/", {"status": "preparing", "ids": [ids[2], ids[0], 999999]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Application.objects.get(pk=ids[0]).position, 0)  # unknown/foreign ids are ignored; 2 isn't in 'preparing'
        self.assertEqual(self.client.post(f"/api/applications/{ids[1]}/move/", {"status": "bogus"}, format="json").status_code, 400)

    def test_authorization(self):
        aid = self.create().json()["id"]
        _, other = self.make_user("o@example.com")
        for m, p in [("get", f"/api/applications/{aid}/"), ("patch", f"/api/applications/{aid}/"), ("delete", f"/api/applications/{aid}/"),
                     ("post", f"/api/applications/{aid}/move/"), ("post", f"/api/applications/{aid}/prepare/"), ("post", f"/api/applications/{aid}/review/")]:
            self.assertEqual(getattr(other, m)(p, {}, format="json").status_code, 404, p)
        self.assertEqual(other.get("/api/applications/").json()["results"], [])
        self.assertEqual(other.post("/api/applications/", {"job_id": self.job.id, "resume_id": 1}, format="json").status_code, 404)  # someone else's resume

    def test_assisted_apply_full_workflow_with_extension(self):
        aid = self.create().json()["id"]
        # 1. prepare: checklist + exact form data, nothing submitted
        p = self.client.post(f"/api/applications/{aid}/prepare/").json()
        self.assertTrue(p["eligibility"]["ready"], p["eligibility"])
        self.assertEqual(p["form_data"]["email"], "asha@example.com")
        self.assertEqual(p["form_data"]["linkedin"], "https://linkedin.com/in/asha")
        self.assertEqual(p["attempt"]["state"], "prepared")
        key = self.client.get("/api/profile/autofill-key/").json()["autofill_key"]
        ext = APIClient()
        # extension sees nothing until the person has reviewed
        self.assertIsNone(ext.get("/api/autofill/profile/", HTTP_X_AUTOFILL_KEY=key).json()["attempt"])
        # 2. review
        self.assertEqual(self.client.post(f"/api/applications/{aid}/review/", {}, format="json").status_code, 200)
        data = ext.get("/api/autofill/profile/", HTTP_X_AUTOFILL_KEY=key).json()
        self.assertEqual(data["attempt"]["application_id"], aid)
        self.assertEqual(data["fields"]["first_name"], "Asha")
        # 3. extension reports what it filled
        rep = ext.post("/api/autofill/report/", {"attempt_id": data["attempt"]["id"], "host": "boards.greenhouse.io", "filled": ["first_name", "email"], "skipped": ["resume"]},
                       format="json", HTTP_X_AUTOFILL_KEY=key)
        self.assertEqual(rep.json()["state"], "autofilled")
        detail = self.client.get(f"/api/applications/{aid}/").json()
        self.assertEqual(detail["status"], "preparing")  # autofill never marks the application as applied
        self.assertIn("autofill", [a["kind"] for a in detail["activities"]])
        # 4. person submits on the site, then confirms
        done = self.client.post(f"/api/applications/{aid}/confirm-submitted/", {"confirm_submitted": True}, format="json")
        self.assertEqual(done.json()["status"], "applied")
        self.assertEqual(self.client.get(f"/api/applications/{aid}/").json()["attempts"][0]["state"], "completed")
        self.assertEqual(self.client.post(f"/api/applications/{aid}/prepare/").status_code, 409)

    def test_confirm_endpoint_needs_flag(self):
        aid = self.create().json()["id"]
        self.assertEqual(self.client.post(f"/api/applications/{aid}/confirm-submitted/", {}, format="json").status_code, 400)

    def test_cancel_and_retry_safely(self):
        aid = self.create().json()["id"]
        t1 = self.client.post(f"/api/applications/{aid}/prepare/").json()["attempt"]["id"]
        self.assertEqual(self.client.post(f"/api/applications/{aid}/attempts/{t1}/retry/").status_code, 409)  # active attempt exists
        self.assertEqual(self.client.post(f"/api/applications/{aid}/attempts/{t1}/cancel/").json()["state"], "cancelled")
        self.assertEqual(self.client.post(f"/api/applications/{aid}/attempts/{t1}/cancel/").status_code, 409)
        key = self.client.get("/api/profile/autofill-key/").json()["autofill_key"]
        rep = APIClient().post("/api/autofill/report/", {"attempt_id": t1, "filled": ["email"]}, format="json", HTTP_X_AUTOFILL_KEY=key)
        self.assertEqual(rep.status_code, 409)  # cancelled attempts cannot be reported on
        for n in range(2, 6):
            r = self.client.post(f"/api/applications/{aid}/attempts/{t1}/retry/")
            self.assertEqual(r.status_code, 201, (n, r.content))
            self.client.post(f"/api/applications/{aid}/attempts/{r.json()['id']}/cancel/")
        self.assertEqual(self.client.post(f"/api/applications/{aid}/attempts/{t1}/retry/").status_code, 409)  # capped

    def test_review_warnings_must_be_acknowledged(self):
        far = mk_job("Principal Engineer", "Omega", "Kubernetes Terraform AWS. 12+ years.", location="Berlin", external_id="far", min_experience=12)
        aid = self.client.post("/api/applications/", {"job_id": far.id}, format="json").json()["id"]
        p = self.client.post(f"/api/applications/{aid}/prepare/").json()
        self.assertTrue(p["eligibility"]["warnings"])
        r = self.client.post(f"/api/applications/{aid}/review/", {}, format="json")
        self.assertEqual((r.status_code, r.json()["code"]), (400, "warnings"))
        self.assertEqual(self.client.post(f"/api/applications/{aid}/review/", {"acknowledge_warnings": True}, format="json").status_code, 200)

    def test_changing_resume_or_letter_requires_re_review(self):
        aid = self.create().json()["id"]
        self.client.post(f"/api/applications/{aid}/prepare/")
        self.client.post(f"/api/applications/{aid}/review/", {}, format="json")
        self.assertIsNotNone(Application.objects.get(pk=aid).review_confirmed_at)
        self.client.patch(f"/api/applications/{aid}/", {"cover_letter": "Edited"}, format="json")
        self.assertIsNone(Application.objects.get(pk=aid).review_confirmed_at)

    def test_autofill_key_security(self):
        ext = APIClient()
        self.assertEqual(ext.get("/api/autofill/profile/").status_code, 401)
        self.assertEqual(ext.get("/api/autofill/profile/", HTTP_X_AUTOFILL_KEY="wrong").status_code, 401)
        key = self.client.get("/api/profile/autofill-key/").json()["autofill_key"]
        self.assertEqual(ext.get("/api/autofill/profile/", HTTP_X_AUTOFILL_KEY=key).status_code, 200)
        # the scoped key cannot be used as a general API credential
        self.assertEqual(ext.get("/api/me/", HTTP_X_AUTOFILL_KEY=key).status_code, 401)
        self.assertEqual(ext.get("/api/resumes/", HTTP_X_AUTOFILL_KEY=key).status_code, 401)
        new = self.client.post("/api/profile/autofill-key/").json()["autofill_key"]
        self.assertNotEqual(new, key)
        self.assertEqual(ext.get("/api/autofill/profile/", HTTP_X_AUTOFILL_KEY=key).status_code, 401)
        self.assertNotIn("autofill_key", self.client.get("/api/me/").content.decode())

    def test_reminders_become_notifications(self):
        aid = self.create().json()["id"]
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        future = (timezone.now() + timedelta(days=3)).isoformat()
        r1 = self.client.post("/api/reminders/", {"title": "Call recruiter", "due_at": past, "application_id": aid}, format="json")
        self.assertEqual(r1.status_code, 201, r1.content)
        self.client.post("/api/reminders/", {"title": "Later", "due_at": future}, format="json")
        self.assertEqual(self.client.post("/api/reminders/", {"title": "", "due_at": past}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/reminders/", {"title": "x", "due_at": "not-a-date"}, format="json").status_code, 400)
        listed = self.client.get("/api/reminders/").json()
        self.assertTrue(next(r for r in listed if r["title"] == "Call recruiter")["overdue"])
        n = self.client.get("/api/notifications/").json()
        self.assertTrue(any(x["title"] == "Call recruiter" for x in n["results"]))
        self.assertEqual(len([x for x in self.client.get("/api/notifications/").json()["results"] if x["title"] == "Call recruiter"]), 1)  # no duplicates
        self.client.post("/api/notifications/", {}, format="json")
        self.assertEqual(self.client.get("/api/notifications/").json()["unread"], 0)
        rid = r1.json()["id"]
        self.assertTrue(self.client.patch(f"/api/reminders/{rid}/", {"done": True}, format="json").json()["done"])
        _, other = self.make_user("x@example.com")
        self.assertEqual(other.patch(f"/api/reminders/{rid}/", {"done": False}, format="json").status_code, 404)
        self.assertEqual(Reminder.objects.get(pk=rid).done, True)

    def test_dashboard(self):
        aid = self.create().json()["id"]
        self.client.post(f"/api/applications/{aid}/move/", {"status": "applied", "confirm_submitted": True}, format="json")
        d = self.client.get("/api/dashboard/").json()
        self.assertEqual(d["counts"]["applied"], 1)
        self.assertEqual(d["total_applications"], 1)
        self.assertEqual(len(d["weekly"]), 8)
        self.assertEqual(sum(w["applied"] for w in d["weekly"]), 1)
        self.assertGreater(d["profile_completeness"]["percent"], 30)
        self.assertFalse(d["ai"]["ready"])

    def test_cover_letter_fallback_is_truthful_and_saved(self):
        aid = self.create().json()["id"]
        r = self.client.post("/api/writing/generate/", {"application_id": aid, "kind": "cover_letter", "save": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        out = r.json()
        self.assertEqual(out["engine"], "rules")
        self.assertIn("Acme", out["text"])
        self.assertIn("Python Developer", out["text"])
        self.assertTrue(out["saved_to_application"])
        self.assertEqual(self.client.get(f"/api/applications/{aid}/").json()["cover_letter"], out["text"])
        self.assertNotIn("Kubernetes", out["text"])  # only skills the candidate has
        for kind in ("recruiter_message", "follow_up", "thank_you"):
            self.assertEqual(self.client.post("/api/writing/generate/", {"application_id": aid, "kind": kind}, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/writing/generate/", {}, format="json").status_code, 400)

    def test_resume_deletion_keeps_application_history(self):
        aid = self.create().json()["id"]
        rid = self.client.get("/api/resumes/").json()[0]["id"]
        self.client.delete(f"/api/resumes/{rid}/")
        a = self.client.get(f"/api/applications/{aid}/").json()
        self.assertIsNone(a["resume_id"])
        self.assertEqual(a["job_title"], "Python Developer")
