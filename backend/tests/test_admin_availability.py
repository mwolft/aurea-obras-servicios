import os
import unittest
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import User


class AdminAuthorizationTestCase(unittest.TestCase):
    @staticmethod
    def create_test_app(app_env: str):
        with patch.dict(
            os.environ,
            {
                "APP_ENV": app_env,
                "DATABASE_URL": "sqlite:///:memory:",
                "SECRET_KEY": "admin-test-secret",
                "FRONTEND_ORIGIN": "https://www.example.test",
                "CLOUDINARY_CLOUD_NAME": "test-cloud",
                "CLOUDINARY_API_KEY": "test-key",
                "CLOUDINARY_API_SECRET": "test-secret",
            },
            clear=False,
        ):
            return create_app()

    def setUp(self):
        self.app = self.create_test_app("development")
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def authenticate(self, is_admin: bool = False):
        user = User(name="Admin test", email=f"admin-{is_admin}@example.com", is_admin=is_admin)
        db.session.add(user)
        db.session.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = user.id

    def test_unauthenticated_users_are_redirected_to_the_frontend_login(self):
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "https://www.example.test/login")

    def test_authenticated_non_admin_receives_forbidden_response(self):
        self.authenticate(is_admin=False)

        self.assertEqual(self.client.get("/admin/").status_code, 403)

    def test_admin_can_access_all_registered_admin_views(self):
        self.authenticate(is_admin=True)

        for path in (
            "/admin/",
            "/admin/tool/",
            "/admin/toolimage/",
            "/admin/reservation/",
            "/admin/toolblock/",
            "/admin/calendar/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_production_registers_the_same_protected_admin(self):
        app = self.create_test_app("production")
        with app.app_context():
            db.create_all()
            try:
                client = app.test_client()
                self.assertEqual(client.get("/admin/").status_code, 302)

                user = User(name="Production admin", email="production-admin@example.com", is_admin=True)
                db.session.add(user)
                db.session.commit()
                with client.session_transaction() as session:
                    session["user_id"] = user.id

                self.assertEqual(client.get("/admin/").status_code, 200)
            finally:
                db.session.remove()
                db.drop_all()
