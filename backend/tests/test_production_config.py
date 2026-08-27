import os
import unittest
from unittest.mock import patch

from app import create_app
from app.config import load_config
from app.extensions import db


PRODUCTION_ENVIRONMENT = {
    "APP_ENV": "production",
    "DATABASE_URL": "sqlite:///:memory:",
    "SECRET_KEY": "production-test-secret",
    "FRONTEND_ORIGIN": "https://www.example.test",
    "CLOUDINARY_CLOUD_NAME": "test-cloud",
    "CLOUDINARY_API_KEY": "test-key",
    "CLOUDINARY_API_SECRET": "test-secret",
}


class ProductionConfigurationTestCase(unittest.TestCase):
    def load_production_config(self, **overrides):
        environment = {**PRODUCTION_ENVIRONMENT, **overrides}
        with patch.dict(os.environ, environment, clear=True):
            return load_config()

    def create_production_app(self, **overrides):
        environment = {**PRODUCTION_ENVIRONMENT, **overrides}
        with patch.dict(os.environ, environment, clear=True):
            return create_app()

    def test_production_requires_frontend_origin_and_cloudinary_configuration(self):
        with self.assertRaisesRegex(RuntimeError, "FRONTEND_ORIGIN"):
            self.load_production_config(FRONTEND_ORIGIN="")

        with self.assertRaisesRegex(RuntimeError, "Cloudinary"):
            self.load_production_config(CLOUDINARY_API_SECRET="")

    def test_google_oauth_configuration_must_be_complete_when_enabled(self):
        with self.assertRaisesRegex(RuntimeError, "Google OAuth"):
            self.load_production_config(GOOGLE_CLIENT_ID="google-client-id")

        config = self.load_production_config(
            GOOGLE_CLIENT_ID="google-client-id",
            GOOGLE_CLIENT_SECRET="google-client-secret",
            GOOGLE_REDIRECT_URI="https://api.example.test/api/auth/google/callback",
        )
        self.assertEqual(config["GOOGLE_CLIENT_ID"], "google-client-id")

    def test_production_cookie_and_debug_configuration(self):
        config = self.load_production_config()

        self.assertFalse(config["DEBUG"])
        self.assertTrue(config["SESSION_COOKIE_HTTPONLY"])
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertEqual(config["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_production_session_cookie_is_secure_and_httponly(self):
        app = self.create_production_app()
        with app.app_context():
            db.create_all()
            try:
                response = app.test_client().post(
                    "/api/auth/register",
                    json={
                        "name": "Production Cookie User",
                        "email": "cookie@example.com",
                        "password": "secure-password",
                    },
                )
                cookie = response.headers["Set-Cookie"]
                self.assertEqual(response.status_code, 201)
                self.assertIn("HttpOnly", cookie)
                self.assertIn("Secure", cookie)
                self.assertIn("SameSite=Lax", cookie)
            finally:
                db.session.remove()
                db.drop_all()

    def test_production_protects_admin_and_keeps_health_public(self):
        app = self.create_production_app()
        client = app.test_client()

        self.assertEqual(client.get("/admin/").status_code, 302)
        self.assertEqual(client.get("/admin/").headers["Location"], "https://www.example.test/login")
        health = client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json(), {"status": "ok"})

    def test_cors_allows_only_configured_frontend_for_preflight(self):
        app = self.create_production_app()
        client = app.test_client()

        allowed = client.open(
            "/api/auth/login",
            method="OPTIONS",
            headers={"Origin": "https://www.example.test"},
        )
        denied = client.open(
            "/api/auth/login",
            method="OPTIONS",
            headers={"Origin": "https://untrusted.example"},
        )

        self.assertEqual(allowed.headers.get("Access-Control-Allow-Origin"), "https://www.example.test")
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Methods"), "GET, POST, OPTIONS")
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Headers"), "Content-Type")
        self.assertEqual(denied.headers.get("Access-Control-Allow-Origin"), None)
        self.assertEqual(denied.headers.get("Access-Control-Allow-Credentials"), None)
