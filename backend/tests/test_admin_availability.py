import os
import re
import unittest
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash


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

    @staticmethod
    def csrf_token(response):
        match = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', response.get_data(as_text=True))
        if match is None:
            raise AssertionError("CSRF token not found in response.")
        return match.group(1)

    def test_unauthenticated_users_are_redirected_to_admin_login(self):
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin/login")

    def test_admin_login_authenticates_only_administrators_and_logout_clears_session(self):
        admin = User(
            name="Administrative User",
            email="admin@example.com",
            password_hash=generate_password_hash("secure-password"),
            is_admin=True,
        )
        regular_user = User(
            name="Regular User",
            email="regular@example.com",
            password_hash=generate_password_hash("secure-password"),
            is_admin=False,
        )
        db.session.add_all((admin, regular_user))
        db.session.commit()

        login_page = self.client.get("/admin/login")
        self.assertEqual(login_page.status_code, 200)
        csrf_token = self.csrf_token(login_page)

        invalid = self.client.post("/admin/login", data={"email": "admin@example.com", "password": "wrong", "csrf_token": csrf_token})
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("Credenciales incorrectas o acceso no autorizado.", invalid.get_data(as_text=True))

        login_page = self.client.get("/admin/login")
        regular = self.client.post("/admin/login", data={"email": "regular@example.com", "password": "secure-password", "csrf_token": self.csrf_token(login_page)})
        self.assertEqual(regular.status_code, 200)
        self.assertIn("Credenciales incorrectas o acceso no autorizado.", regular.get_data(as_text=True))

        login_page = self.client.get("/admin/login")
        unknown = self.client.post("/admin/login", data={"email": "unknown@example.com", "password": "secure-password", "csrf_token": self.csrf_token(login_page)})
        self.assertEqual(unknown.status_code, 200)
        self.assertIn("Credenciales incorrectas o acceso no autorizado.", unknown.get_data(as_text=True))

        login_page = self.client.get("/admin/login")
        authenticated = self.client.post("/admin/login", data={"email": "ADMIN@EXAMPLE.COM", "password": "secure-password", "csrf_token": self.csrf_token(login_page)})
        self.assertEqual(authenticated.status_code, 302)
        self.assertEqual(authenticated.headers["Location"], "/admin/")
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(self.client.get("/admin/login").status_code, 302)

        admin_page = self.client.get("/admin/")
        logout = self.client.post("/admin/logout", data={"csrf_token": self.csrf_token(admin_page)})
        self.assertEqual(logout.status_code, 302)
        self.assertEqual(logout.headers["Location"], "/admin/login")
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_admin_login_rejects_missing_csrf_token(self):
        response = self.client.post("/admin/login", data={"email": "admin@example.com", "password": "secure-password"})

        self.assertEqual(response.status_code, 400)

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

    def test_admin_navigation_uses_spanish_labels(self):
        self.authenticate(is_admin=True)

        response = self.client.get("/admin/")
        content = response.get_data(as_text=True)

        for label in ("Inicio", "Herramientas", "Fotografías", "Bloqueos", "Reservas", "Cerrar sesión"):
            with self.subTest(label=label):
                self.assertIn(label, content)

    def test_production_registers_the_same_protected_admin(self):
        app = self.create_test_app("production")
        with app.app_context():
            db.create_all()
            try:
                client = app.test_client()
                self.assertEqual(client.get("/admin/").status_code, 302)
                self.assertEqual(client.get("/admin/login").status_code, 200)

                user = User(name="Production admin", email="production-admin@example.com", is_admin=True)
                db.session.add(user)
                db.session.commit()
                with client.session_transaction() as session:
                    session["user_id"] = user.id

                self.assertEqual(client.get("/admin/").status_code, 200)
            finally:
                db.session.remove()
                db.drop_all()
