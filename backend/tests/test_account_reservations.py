import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "account-reservations-test-secret"

from app import create_app
from app.extensions import db
from app.models import Reservation, Tool, User


class AccountReservationsApiTestCase(unittest.TestCase):
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

    def create_user(self, email: str) -> User:
        user = User(name=email.split("@")[0], email=email, password_hash="unused")
        db.session.add(user)
        db.session.commit()
        return user

    def create_tool(self, name: str) -> Tool:
        tool = Tool(
            name=name,
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=Decimal("20.00"),
            pickup_available=True,
            delivery_available=True,
            is_published=True,
            is_available=True,
        )
        db.session.add(tool)
        db.session.commit()
        return tool

    def create_reservation(self, tool: Tool, user_id: int | None, **overrides) -> Reservation:
        values = {
            "tool_id": tool.id,
            "user_id": user_id,
            "start_date": date(2026, 9, 10),
            "end_date": date(2026, 9, 12),
            "status": "confirmed",
            "fulfillment_method": "pickup",
            "customer_name": "Customer",
            "customer_email": "customer@example.com",
            "customer_phone": "600000000",
            "terms_accepted": True,
            "privacy_accepted": True,
            "charged_days": 3,
            "rental_amount": Decimal("30.00"),
            "delivery_amount": Decimal("0.00"),
            "total_amount": Decimal("30.00"),
        }
        values.update(overrides)
        reservation = Reservation(**values)
        db.session.add(reservation)
        db.session.commit()
        return reservation

    def authenticate_as(self, user: User) -> None:
        with self.client.session_transaction() as session:
            session["user_id"] = user.id

    def test_requires_an_authenticated_session(self):
        self.assertEqual(self.client.get("/api/account/reservations").status_code, 401)

    def test_lists_only_current_users_reservations_and_excludes_guests(self):
        user_a = self.create_user("a@example.com")
        user_b = self.create_user("b@example.com")
        tool_a = self.create_tool("Tool A")
        tool_b = self.create_tool("Tool B")
        own = self.create_reservation(tool_a, user_a.id)
        self.create_reservation(tool_b, user_b.id)
        self.create_reservation(tool_b, None)
        self.authenticate_as(user_a)

        response = self.client.get("/api/account/reservations")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 1)
        self.assertEqual(response.get_json()[0]["id"], own.id)
        self.assertEqual(response.get_json()[0]["tool"], {"id": tool_a.id, "name": "Tool A"})

    def test_orders_newest_first_and_serializes_decimals_as_strings(self):
        user = self.create_user("user@example.com")
        tool = self.create_tool("Tool")
        older = self.create_reservation(tool, user.id)
        newer = self.create_reservation(
            tool,
            user.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 3),
        )
        self.authenticate_as(user)

        response = self.client.get("/api/account/reservations")

        body = response.get_json()
        self.assertEqual([item["id"] for item in body], [newer.id, older.id])
        self.assertEqual(body[0]["rental_amount"], "30.00")
        self.assertEqual(body[0]["total_amount"], "30.00")

    def test_expired_pending_payment_is_marked_without_mutating_status(self):
        user = self.create_user("user@example.com")
        tool = self.create_tool("Tool")
        reservation = self.create_reservation(
            tool,
            user.id,
            status="pending_payment",
            payment_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        self.authenticate_as(user)

        response = self.client.get("/api/account/reservations")

        self.assertTrue(response.get_json()[0]["payment_expired"])
        self.assertEqual(db.session.get(Reservation, reservation.id).status, "pending_payment")

    def test_delivery_address_is_only_returned_for_owned_delivery_reservation(self):
        user = self.create_user("user@example.com")
        tool = self.create_tool("Tool")
        self.create_reservation(
            tool,
            user.id,
            fulfillment_method="delivery",
            delivery_address="Calle propia 1",
            delivery_amount=Decimal("12.50"),
            total_amount=Decimal("42.50"),
        )
        self.authenticate_as(user)

        response = self.client.get("/api/account/reservations")

        self.assertEqual(response.get_json()[0]["delivery_address"], "Calle propia 1")

    def test_detail_requires_an_authenticated_session(self):
        user = self.create_user("user@example.com")
        tool = self.create_tool("Tool")
        reservation = self.create_reservation(tool, user.id)

        response = self.client.get(f"/api/account/reservations/{reservation.id}")

        self.assertEqual(response.status_code, 401)

    def test_detail_returns_only_the_current_users_reservation(self):
        user_a = self.create_user("a@example.com")
        user_b = self.create_user("b@example.com")
        tool = self.create_tool("Tool")
        own = self.create_reservation(
            tool,
            user_a.id,
            fulfillment_method="delivery",
            delivery_address="Calle propia 1",
            billable_km=Decimal("18.50"),
            daily_price_snapshot=Decimal("10.00"),
            delivery_price_per_km_snapshot=Decimal("0.50"),
            delivery_amount=Decimal("9.25"),
            total_amount=Decimal("39.25"),
        )
        other = self.create_reservation(tool, user_b.id, start_date=date(2026, 10, 1), end_date=date(2026, 10, 3))
        self.authenticate_as(user_a)

        own_response = self.client.get(f"/api/account/reservations/{own.id}")
        other_response = self.client.get(f"/api/account/reservations/{other.id}")

        self.assertEqual(own_response.status_code, 200)
        body = own_response.get_json()
        self.assertEqual(body["tool"], {"id": tool.id, "name": "Tool"})
        self.assertEqual(body["billable_km"], "18.50")
        self.assertEqual(body["daily_price_snapshot"], "10.00")
        self.assertEqual(body["delivery_price_per_km_snapshot"], "0.50")
        self.assertEqual(body["customer_name"], "Customer")
        self.assertEqual(body["customer_email"], "customer@example.com")
        self.assertEqual(body["customer_phone"], "600000000")
        self.assertNotIn("user_id", body)
        self.assertNotIn("password_hash", body)
        self.assertEqual(other_response.status_code, 404)

    def test_guest_reservation_is_not_available_as_account_detail(self):
        user = self.create_user("user@example.com")
        tool = self.create_tool("Tool")
        guest_reservation = self.create_reservation(tool, None)
        self.authenticate_as(user)

        response = self.client.get(f"/api/account/reservations/{guest_reservation.id}")

        self.assertEqual(response.status_code, 404)

    def test_expired_pending_payment_is_marked_in_detail_without_mutating_status(self):
        user = self.create_user("user@example.com")
        tool = self.create_tool("Tool")
        reservation = self.create_reservation(
            tool,
            user.id,
            status="pending_payment",
            payment_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        self.authenticate_as(user)

        response = self.client.get(f"/api/account/reservations/{reservation.id}")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["payment_expired"])
        self.assertEqual(db.session.get(Reservation, reservation.id).status, "pending_payment")
