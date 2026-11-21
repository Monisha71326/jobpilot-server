from rest_framework.test import APIClient

from .base import APITestCase, User


class AuthTests(APITestCase):
    def test_register_login_logout(self):
        c = APIClient()
        r = c.post("/api/auth/register/", {"email": "New@Example.com", "password": "Correct-horse-9", "first_name": "N"})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(User.objects.filter(username="new@example.com").exists())
        self.assertTrue(User.objects.get(username="new@example.com").profile)
        token = r.json()["token"]
        c.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(c.get("/api/me/").status_code, 200)
        self.assertEqual(c.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(c.get("/api/me/").status_code, 401)
        r = APIClient().post("/api/auth/login/", {"email": "new@example.com", "password": "Correct-horse-9"})
        self.assertEqual(r.status_code, 200)

    def test_duplicate_email_and_weak_password(self):
        c = APIClient()
        self.assertEqual(c.post("/api/auth/register/", {"email": "ASHA@example.com", "password": "Correct-horse-9"}).status_code, 400)
        self.assertEqual(c.post("/api/auth/register/", {"email": "x@example.com", "password": "12345678"}).status_code, 400)

    def test_bad_login_is_generic(self):
        r = APIClient().post("/api/auth/login/", {"email": "asha@example.com", "password": "nope-nope-nope"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["detail"], "Invalid email or password.")

    def test_protected_endpoints_need_auth(self):
        c = APIClient()
        for path in ["/api/me/", "/api/resumes/", "/api/jobs/", "/api/applications/", "/api/dashboard/", "/api/interviews/"]:
            self.assertEqual(c.get(path).status_code, 401, path)

    def test_profile_update_validation(self):
        r = self.client.patch("/api/profile/", {"skills": ["python", "Django", "python"], "years_experience": "3.5",
                                                "links": {"github": "https://github.com/x", "evil": "x"}}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["skills"], ["Python", "Django"])
        self.assertEqual(r.json()["links"], {"github": "https://github.com/x"})
        self.assertEqual(self.client.patch("/api/profile/", {"links": {"github": "javascript:alert(1)"}}, format="json").status_code, 400)
        self.assertEqual(self.client.patch("/api/profile/", {"years_experience": "99"}, format="json").status_code, 400)

    def test_password_change_and_account_deletion(self):
        r = self.client.post("/api/auth/password/", {"old_password": self.password, "new_password": "Another-good-pass-1"})
        self.assertEqual(r.status_code, 200)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Token {r.json()['token']}")
        self.assertEqual(c.delete("/api/me/", {"password": "wrong"}, format="json").status_code, 400)
        self.upload_resume(c)
        self.assertEqual(c.delete("/api/me/", {"password": "Another-good-pass-1"}, format="json").status_code, 204)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())


class SpaServingTests(APITestCase):
    def test_unknown_route_serves_index_or_clear_404_and_api_stays_json(self):
        c = APIClient()
        r = c.get("/dashboard")
        self.assertIn(r.status_code, (200, 404))  # 200 when frontend/dist is built
        r = c.get("/api/nope/")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b"<html", r.content[:200].lower())
