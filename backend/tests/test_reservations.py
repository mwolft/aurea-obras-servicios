import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "reservation-test-secret"

from app import create_app
from app.extensions import db
from app.models import Reservation, Tool
from app.services.availability import is_tool_available
from app.services.reservations import review_delivery_reservation


class ReservationApiTestCase(unittest.TestCase):
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

    def create_tool(self, **overrides):
        values = {
            "name": "Reservation tool",
            "category": "Demo",
            "daily_price": Decimal("10.00"),
            "deposit_amount": Decimal("25.00"),
            "pickup_available": True,
            "delivery_available": True,
            "delivery_price_per_km": Decimal("1.50"),
            "is_published": True,
            "is_available": True,
        }
        values.update(overrides)
        tool = Tool(**values)
        db.session.add(tool)
        db.session.commit()
        return tool

    @staticmethod
    def create_reservation(tool, start_date, end_date, status="confirmed", payment_expires_at=None):
        values = {
            "tool_id": tool.id,
            "start_date": start_date,
            "end_date": end_date,
            "status": status,
            "customer_name": "Customer Test",
            "customer_email": "customer@example.com",
            "customer_phone": "600000000",
            "terms_accepted": True,
            "privacy_accepted": True,
        }
        if status == "pending_payment":
            values.update(
                {
                    "fulfillment_method": "pickup",
                    "payment_expires_at": payment_expires_at
                    or datetime.now(timezone.utc) + timedelta(minutes=10),
                }
            )
        elif status == "pending_review":
            values.update(
                {
                    "fulfillment_method": "delivery",
                    "delivery_address": "Calle de prueba 1",
                    "payment_expires_at": None,
                }
            )
        else:
            values["payment_expires_at"] = payment_expires_at

        reservation = Reservation(**values)
        db.session.add(reservation)
        db.session.commit()
        return reservation

    @staticmethod
    def request_payload(**overrides):
        values = {
            "start_date": "2026-08-20",
            "end_date": "2026-08-22",
            "customer_name": "Customer Test",
            "customer_email": "customer@example.com",
            "customer_phone": "600000000",
            "terms_accepted": True,
            "privacy_accepted": True,
            "fulfillment_method": "pickup",
        }
        values.update(overrides)
        return values

    def create_request(self, tool, **overrides):
        tool_id = tool.id
        db.session.remove()
        return self.client.post(
            f"/api/tools/{tool_id}/reservations", json=self.request_payload(**overrides)
        )

    def test_pickup_creates_pending_payment_with_quote_and_expiration(self):
        tool = self.create_tool()

        response = self.create_request(tool)

        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["status"], "pending_payment")
        self.assertEqual(body["fulfillment_method"], "pickup")
        self.assertEqual(body["charged_days"], 3)
        self.assertEqual(body["daily_price_snapshot"], "10.00")
        self.assertIsNone(body["delivery_price_per_km_snapshot"])
        self.assertEqual(body["rental_amount"], "30.00")
        self.assertEqual(body["delivery_amount"], "0.00")
        self.assertEqual(body["total_amount"], "30.00")
        self.assertEqual(body["deposit_amount"], "25.00")
        payment_expires_at = datetime.fromisoformat(body["payment_expires_at"])
        if payment_expires_at.tzinfo is None:
            payment_expires_at = payment_expires_at.replace(tzinfo=timezone.utc)
        self.assertAlmostEqual(
            (payment_expires_at - datetime.now(timezone.utc)).total_seconds(), 15 * 60, delta=5
        )

    def test_delivery_requires_address(self):
        tool = self.create_tool()

        response = self.create_request(tool, fulfillment_method="delivery")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "delivery_address is required.")

    def test_delivery_creates_pending_review_without_quote_or_expiration(self):
        tool = self.create_tool()

        response = self.create_request(
            tool,
            fulfillment_method="delivery",
            delivery_address="Calle de prueba 1, Madrid",
        )

        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["status"], "pending_review")
        self.assertIsNone(body["payment_expires_at"])
        self.assertIsNone(body["charged_days"])
        self.assertIsNone(body["rental_amount"])
        self.assertIsNone(body["delivery_amount"])
        self.assertIsNone(body["total_amount"])

    def test_public_request_cannot_set_kilometres_or_amounts(self):
        tool = self.create_tool()

        response = self.create_request(
            tool,
            billable_km="999.99",
            daily_price_snapshot="0.01",
            rental_amount="0.01",
            delivery_amount="0.01",
            total_amount="0.01",
        )

        self.assertEqual(response.status_code, 201)
        reservation = db.session.get(Reservation, response.get_json()["id"])
        self.assertIsNone(reservation.billable_km)
        self.assertEqual(reservation.rental_amount, Decimal("30.00"))
        self.assertEqual(reservation.delivery_amount, Decimal("0.00"))
        self.assertEqual(reservation.total_amount, Decimal("30.00"))

    def test_pending_review_blocks_availability(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 20), date(2026, 8, 22), status="pending_review")

        self.assertFalse(is_tool_available(tool, date(2026, 8, 20), date(2026, 8, 22)))

    def test_delivery_review_freezes_quote_and_starts_payment_window(self):
        tool = self.create_tool()
        response = self.create_request(
            tool,
            fulfillment_method="delivery",
            delivery_address="Calle de prueba 1, Madrid",
        )
        reservation_id = response.get_json()["id"]
        review_time = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        db.session.remove()

        reservation = review_delivery_reservation(
            reservation_id, Decimal("12.50"), now=review_time
        )

        self.assertEqual(reservation.status, "pending_payment")
        self.assertEqual(reservation.billable_km, Decimal("12.50"))
        self.assertEqual(reservation.charged_days, 3)
        self.assertEqual(reservation.rental_amount, Decimal("30.00"))
        self.assertEqual(reservation.delivery_amount, Decimal("18.75"))
        self.assertEqual(reservation.total_amount, Decimal("48.75"))
        payment_expires_at = reservation.payment_expires_at
        if payment_expires_at.tzinfo is None:
            payment_expires_at = payment_expires_at.replace(tzinfo=timezone.utc)
        self.assertEqual(payment_expires_at, review_time + timedelta(minutes=15))

    def test_snapshots_do_not_change_when_tool_prices_change(self):
        tool = self.create_tool()
        response = self.create_request(tool)
        reservation = db.session.get(Reservation, response.get_json()["id"])

        tool.daily_price = Decimal("99.00")
        tool.delivery_price_per_km = Decimal("99.00")
        db.session.commit()
        db.session.refresh(reservation)

        self.assertEqual(reservation.daily_price_snapshot, Decimal("10.00"))
        self.assertEqual(reservation.rental_amount, Decimal("30.00"))
        self.assertEqual(reservation.total_amount, Decimal("30.00"))

    def test_deposit_is_informative_and_excluded_from_total(self):
        tool = self.create_tool(deposit_amount=Decimal("125.00"))

        response = self.create_request(tool)

        self.assertEqual(response.get_json()["deposit_amount"], "125.00")
        self.assertEqual(response.get_json()["total_amount"], "30.00")

    def test_confirmed_overlapping_reservation_returns_conflict(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 20), date(2026, 8, 22))

        response = self.create_request(tool, start_date="2026-08-22", end_date="2026-08-24")

        self.assertEqual(response.status_code, 409)

    def test_cancelled_or_expired_pending_payment_does_not_block_creation(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 20), date(2026, 8, 22), status="cancelled")
        self.create_reservation(
            tool,
            date(2026, 8, 20),
            date(2026, 8, 22),
            status="pending_payment",
            payment_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        response = self.create_request(tool)

        self.assertEqual(response.status_code, 201)

    def test_invalid_input_returns_bad_request(self):
        tool = self.create_tool()

        no_json_response = self.client.post(f"/api/tools/{tool.id}/reservations")
        malformed_date_response = self.create_request(tool, start_date="20-08-2026")
        inverted_range_response = self.create_request(
            tool, start_date="2026-08-22", end_date="2026-08-20"
        )
        invalid_method_response = self.create_request(tool, fulfillment_method="courier")

        self.assertEqual(no_json_response.status_code, 400)
        self.assertEqual(malformed_date_response.status_code, 400)
        self.assertEqual(inverted_range_response.status_code, 400)
        self.assertEqual(invalid_method_response.status_code, 400)

    def test_customer_data_and_acceptances_are_required(self):
        tool = self.create_tool()
        payload = self.request_payload(
            customer_name="",
            customer_email="invalid-email",
            customer_phone="",
            terms_accepted=False,
            privacy_accepted=False,
        )

        missing_name_response = self.client.post(f"/api/tools/{tool.id}/reservations", json=payload)
        payload["customer_name"] = "Customer Test"
        invalid_email_response = self.client.post(f"/api/tools/{tool.id}/reservations", json=payload)
        payload["customer_email"] = "customer@example.com"
        missing_phone_response = self.client.post(f"/api/tools/{tool.id}/reservations", json=payload)
        payload["customer_phone"] = "600000000"
        terms_response = self.client.post(f"/api/tools/{tool.id}/reservations", json=payload)
        payload["terms_accepted"] = True
        privacy_response = self.client.post(f"/api/tools/{tool.id}/reservations", json=payload)

        self.assertEqual(missing_name_response.status_code, 400)
        self.assertEqual(invalid_email_response.status_code, 400)
        self.assertEqual(missing_phone_response.status_code, 400)
        self.assertEqual(terms_response.status_code, 400)
        self.assertEqual(privacy_response.status_code, 400)

    def test_missing_or_unpublished_tool_returns_not_found(self):
        unpublished_tool = self.create_tool(is_published=False)

        unpublished_response = self.create_request(unpublished_tool)
        missing_response = self.client.post(
            "/api/tools/999999/reservations", json=self.request_payload()
        )

        self.assertEqual(unpublished_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
