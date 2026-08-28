import os
import re
import unittest
from decimal import Decimal
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import Tool, User
from werkzeug.security import check_password_hash, generate_password_hash


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

    def create_user(self, email: str, *, is_admin: bool = False, password: str | None = None, google_sub: str | None = None):
        user = User(
            name=email.split("@", 1)[0],
            email=email,
            is_admin=is_admin,
            password_hash=generate_password_hash(password) if password else None,
            google_sub=google_sub,
        )
        db.session.add(user)
        db.session.commit()
        return user

    def authenticate_user(self, user: User):
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
        self.assertEqual(self.client.get("/admin/user/").status_code, 403)

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

        for label in (
            "AUREA",
            "Administración",
            "Admin test",
            "Inicio",
            "Herramientas",
            "Fotografías",
            "Bloqueos",
            "Reservas",
            "Usuarios",
            "Cambiar contraseña",
            "Cerrar sesión",
        ):
            with self.subTest(label=label):
                self.assertIn(label, content)

        self.assertIn('class="aurea-admin-user-icon"', content)
        self.assertIn('class="aurea-admin-logout"', content)
        self.assertIn('class="aurea-admin-topbar-actions"', content)
        self.assertIn('id="aurea-admin-logout-form"', content)
        self.assertIn('form="aurea-admin-logout-form"', content)
        self.assertEqual(content.count('action="/admin/logout"'), 1)
        self.assertIn('data-toggle="dropdown"', content)

    def test_user_admin_is_read_only_and_uses_controlled_access_changes(self):
        administrator = self.create_user("admin@example.com", is_admin=True, password="secure-password")
        target = self.create_user("target@example.com", google_sub="google-subject")
        self.authenticate_user(administrator)

        listing = self.client.get("/admin/user/")
        content = listing.get_data(as_text=True)
        self.assertEqual(listing.status_code, 200)
        self.assertNotIn("password_hash", content)
        self.assertNotIn("google-subject", content)
        self.assertNotIn("Create New Record", content)
        self.assertIn("Google", content)

        grant_page = self.client.get(f"/admin/user/grant-admin-access/{target.id}")
        grant = self.client.post(
            f"/admin/user/grant-admin-access/{target.id}",
            data={"csrf_token": self.csrf_token(grant_page)},
        )
        self.assertEqual(grant.status_code, 302)
        self.assertTrue(db.session.get(User, target.id).is_admin)

        revoke_page = self.client.get(f"/admin/user/revoke-admin-access/{target.id}")
        revoke = self.client.post(
            f"/admin/user/revoke-admin-access/{target.id}",
            data={"csrf_token": self.csrf_token(revoke_page)},
        )
        self.assertEqual(revoke.status_code, 302)
        self.assertFalse(db.session.get(User, target.id).is_admin)

    def test_last_admin_and_self_revocation_are_rejected(self):
        administrator = self.create_user("admin@example.com", is_admin=True, password="secure-password")
        self.authenticate_user(administrator)

        page = self.client.get(f"/admin/user/revoke-admin-access/{administrator.id}")
        response = self.client.post(
            f"/admin/user/revoke-admin-access/{administrator.id}",
            data={"csrf_token": self.csrf_token(page)},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(db.session.get(User, administrator.id).is_admin)
        self.assertIn("No puedes retirar tu propio acceso administrativo.", response.get_data(as_text=True))

    def test_password_change_requires_current_password_but_google_user_can_set_one(self):
        administrator = self.create_user("admin@example.com", is_admin=True, password="secure-password")
        self.authenticate_user(administrator)

        page = self.client.get("/admin/account/")
        invalid = self.client.post(
            "/admin/account/",
            data={
                "csrf_token": self.csrf_token(page),
                "current_password": "wrong-password",
                "new_password": "updated-password",
                "confirm_password": "updated-password",
            },
            follow_redirects=True,
        )
        self.assertIn("La contraseña actual no es correcta.", invalid.get_data(as_text=True))
        self.assertTrue(check_password_hash(db.session.get(User, administrator.id).password_hash, "secure-password"))

        page = self.client.get("/admin/account/")
        updated = self.client.post(
            "/admin/account/",
            data={
                "csrf_token": self.csrf_token(page),
                "current_password": "secure-password",
                "new_password": "updated-password",
                "confirm_password": "updated-password",
            },
        )
        self.assertEqual(updated.status_code, 302)
        self.assertTrue(check_password_hash(db.session.get(User, administrator.id).password_hash, "updated-password"))

        google_admin = self.create_user("google@example.com", is_admin=True, google_sub="google-subject")
        self.authenticate_user(google_admin)
        page = self.client.get("/admin/account/")
        response = self.client.post(
            "/admin/account/",
            data={
                "csrf_token": self.csrf_token(page),
                "new_password": "google-password",
                "confirm_password": "google-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(check_password_hash(db.session.get(User, google_admin.id).password_hash, "google-password"))

    def test_admin_password_change_rejects_missing_csrf_token_and_new_password_works_for_admin_login(self):
        administrator = self.create_user("admin@example.com", is_admin=True, password="secure-password")
        self.authenticate_user(administrator)

        missing_csrf = self.client.post(
            "/admin/account/",
            data={"current_password": "secure-password", "new_password": "updated-password", "confirm_password": "updated-password"},
        )
        self.assertEqual(missing_csrf.status_code, 400)

        page = self.client.get("/admin/account/")
        self.client.post(
            "/admin/account/",
            data={
                "csrf_token": self.csrf_token(page),
                "current_password": "secure-password",
                "new_password": "updated-password",
                "confirm_password": "updated-password",
            },
        )
        self.client.post("/admin/logout", data={"csrf_token": self.csrf_token(self.client.get("/admin/"))})
        login_page = self.client.get("/admin/login")
        login = self.client.post(
            "/admin/login",
            data={"email": "admin@example.com", "password": "updated-password", "csrf_token": self.csrf_token(login_page)},
        )
        self.assertEqual(login.status_code, 302)

    def test_tool_and_image_views_use_spanish_labels(self):
        self.authenticate(is_admin=True)

        tool_response = self.client.get("/admin/tool/")
        image_response = self.client.get("/admin/toolimage/")
        self.assertEqual(tool_response.status_code, 200)
        self.assertEqual(image_response.status_code, 200)
        for label in (
            "Nombre",
            "Categoría",
            "Precio diario",
            "Fianza",
            "Publicada",
            "Disponible",
            "Listado",
            "Crear",
            "Buscar",
            "Añadir filtro",
        ):
            self.assertIn(label, tool_response.get_data(as_text=True))
        for label in ("Herramienta", "Orden", "Creada"):
            self.assertIn(label, image_response.get_data(as_text=True))

    def test_tool_name_is_used_for_image_relationships_and_save_controls_use_guardar(self):
        tool = Tool(
            name="Mini retroexcavadora",
            category="Maquinaria",
            daily_price=Decimal("100.00"),
            deposit_amount=Decimal("250.00"),
            pickup_available=True,
            delivery_available=False,
            is_published=True,
            is_available=True,
        )
        db.session.add(tool)
        db.session.commit()
        self.authenticate(is_admin=True)

        image_form = self.client.get("/admin/toolimage/new/")
        image_content = image_form.get_data(as_text=True)
        tool_form = self.client.get("/admin/tool/new/")
        tool_content = tool_form.get_data(as_text=True)

        self.assertEqual(str(tool), "Mini retroexcavadora")
        self.assertEqual(image_form.status_code, 200)
        self.assertIn("Mini retroexcavadora", image_content)
        self.assertNotIn(f"&lt;Tool {tool.id}&gt;", image_content)
        self.assertIn("1 = imagen principal; 2, 3", image_content)
        for label in ("Guardar", "Guardar y agregar otro", "Guardar y continuar editando", "Cancelar"):
            self.assertIn(label, tool_content)
        self.assertNotIn('value="Salvar"', tool_content)

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
