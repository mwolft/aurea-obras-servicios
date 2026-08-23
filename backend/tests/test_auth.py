import os
import unittest
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "auth-test-secret"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"

from app import create_app
from app.extensions import db
from app.models import Reservation, Tool, User


class AuthenticationApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def credentials(**overrides):
        values = {
            "name": "Aurea Test User",
            "email": "user@example.com",
            "password": "secure-password",
        }
        values.update(overrides)
        return values

    def register(self, **overrides):
        return self.client.post("/api/auth/register", json=self.credentials(**overrides))

    def create_tool(self):
        tool = Tool(
            name="Authenticated reservation tool",
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=Decimal("25.00"),
            pickup_available=True,
            delivery_available=False,
            is_published=True,
            is_available=True,
        )
        db.session.add(tool)
        db.session.commit()
        return tool.id

    @staticmethod
    def reservation_payload(**overrides):
        values = {
            "start_date": "2026-09-10",
            "end_date": "2026-09-12",
            "customer_name": "Reservation Customer",
            "customer_email": "reservation@example.com",
            "customer_phone": "600000000",
            "terms_accepted": True,
            "privacy_accepted": True,
            "fulfillment_method": "pickup",
        }
        values.update(overrides)
        return values

    def test_register_normalizes_email_hashes_password_and_starts_session(self):
        response = self.register(email="USER@Example.COM")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), {"id": 1, "name": "Aurea Test User", "email": "user@example.com"})
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        user = db.session.get(User, 1)
        self.assertEqual(user.email, "user@example.com")
        self.assertNotEqual(user.password_hash, "secure-password")
        self.assertNotIn("secure-password", user.password_hash)
        self.assertEqual(self.client.get("/api/auth/me").get_json()["email"], "user@example.com")

    def test_duplicate_email_is_rejected(self):
        self.assertEqual(self.register().status_code, 201)

        response = self.register(email="USER@example.com")

        self.assertEqual(response.status_code, 409)

    def test_login_rejects_wrong_password_and_accepts_correct_password(self):
        self.assertEqual(self.register().status_code, 201)
        self.client.post("/api/auth/logout")

        wrong_password = self.client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "wrong-pass"},
        )
        correct_password = self.client.post(
            "/api/auth/login",
            json={"email": "USER@example.com", "password": "secure-password"},
        )

        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(correct_password.status_code, 200)
        self.assertEqual(correct_password.get_json()["email"], "user@example.com")

    def test_logout_clears_session_and_me_requires_authentication(self):
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.register().status_code, 201)

        logout = self.client.post("/api/auth/logout")

        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_authenticated_reservation_uses_session_user_and_ignores_client_user_id(self):
        tool_id = self.create_tool()
        other_user = User(name="Other User", email="other@example.com", password_hash="not-used")
        db.session.add(other_user)
        db.session.flush()
        other_user_id = other_user.id
        db.session.commit()
        self.assertEqual(self.register().status_code, 201)
        authenticated_user_id = self.client.get("/api/auth/me").get_json()["id"]
        db.session.remove()

        response = self.client.post(
            f"/api/tools/{tool_id}/reservations",
            json=self.reservation_payload(user_id=other_user_id),
        )

        self.assertEqual(response.status_code, 201)
        reservation = db.session.get(Reservation, response.get_json()["id"])
        self.assertEqual(reservation.user_id, authenticated_user_id)
        self.assertNotEqual(reservation.user_id, other_user_id)

    def test_guest_reservation_keeps_user_id_null(self):
        tool_id = self.create_tool()
        db.session.remove()

        response = self.client.post(
            f"/api/tools/{tool_id}/reservations",
            json=self.reservation_payload(user_id=999999),
        )

        self.assertEqual(response.status_code, 201)
        reservation = db.session.get(Reservation, response.get_json()["id"])
        self.assertIsNone(reservation.user_id)

    def test_cors_credentials_are_limited_to_frontend_origin(self):
        allowed = self.client.open(
            "/api/auth/login",
            method="OPTIONS",
            headers={"Origin": "http://localhost:3000"},
        )
        denied = self.client.open(
            "/api/auth/login",
            method="OPTIONS",
            headers={"Origin": "https://untrusted.example"},
        )

        self.assertEqual(allowed.headers.get("Access-Control-Allow-Origin"), "http://localhost:3000")
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Methods"), "GET, POST, OPTIONS")
        self.assertIsNone(denied.headers.get("Access-Control-Allow-Origin"))
        self.assertIsNone(denied.headers.get("Access-Control-Allow-Credentials"))
