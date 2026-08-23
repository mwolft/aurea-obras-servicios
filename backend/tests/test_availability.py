import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "availability-test-secret"

from app import create_app
from app.extensions import db
from app.models import Reservation, Tool


class ToolAvailabilityApiTestCase(unittest.TestCase):
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
            "name": "Availability tool",
            "category": "Demo",
            "daily_price": Decimal("10.00"),
            "deposit_amount": Decimal("25.00"),
            "pickup_available": True,
            "delivery_available": False,
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
        reservation = Reservation(
            tool_id=tool.id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            customer_name="Customer Test",
            customer_email="customer@example.com",
            customer_phone="600000000",
            terms_accepted=True,
            privacy_accepted=True,
            payment_expires_at=(
                payment_expires_at
                if payment_expires_at is not None
                else datetime.now(timezone.utc) + timedelta(minutes=10)
            ),
        )
        db.session.add(reservation)
        db.session.commit()
        return reservation

    def availability_request(self, tool, start_date, end_date):
        return self.client.get(
            f"/api/tools/{tool.id}/availability",
            query_string={"start_date": start_date, "end_date": end_date},
        )

    def test_tool_without_reservations_is_available(self):
        tool = self.create_tool()

        response = self.availability_request(tool, "2026-08-20", "2026-08-22")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "tool_id": tool.id,
                "start_date": "2026-08-20",
                "end_date": "2026-08-22",
                "available": True,
            },
        )

    def test_unavailable_tool_is_not_available(self):
        tool = self.create_tool(is_available=False)

        response = self.availability_request(tool, "2026-08-20", "2026-08-22")

        self.assertFalse(response.get_json()["available"])

    def test_confirmed_reservation_inside_requested_range_blocks_availability(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 21), date(2026, 8, 21))

        response = self.availability_request(tool, "2026-08-20", "2026-08-22")

        self.assertFalse(response.get_json()["available"])

    def test_overlap_at_requested_start_blocks_availability(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 10), date(2026, 8, 12))

        response = self.availability_request(tool, "2026-08-12", "2026-08-15")

        self.assertFalse(response.get_json()["available"])

    def test_overlap_at_requested_end_blocks_availability(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 10), date(2026, 8, 12))

        response = self.availability_request(tool, "2026-08-08", "2026-08-10")

        self.assertFalse(response.get_json()["available"])

    def test_requested_range_containing_reservation_blocks_availability(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 11), date(2026, 8, 12))

        response = self.availability_request(tool, "2026-08-10", "2026-08-13")

        self.assertFalse(response.get_json()["available"])

    def test_range_outside_confirmed_reservation_is_available(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 10), date(2026, 8, 12))

        response = self.availability_request(tool, "2026-08-13", "2026-08-15")

        self.assertTrue(response.get_json()["available"])

    def test_cancelled_reservation_does_not_block_availability(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 10), date(2026, 8, 12), status="cancelled")

        response = self.availability_request(tool, "2026-08-10", "2026-08-12")

        self.assertTrue(response.get_json()["available"])

    def test_pending_payment_with_valid_expiration_blocks_availability(self):
        tool = self.create_tool()
        self.create_reservation(
            tool,
            date(2026, 8, 10),
            date(2026, 8, 12),
            status="pending_payment",
        )

        response = self.availability_request(tool, "2026-08-10", "2026-08-12")

        self.assertFalse(response.get_json()["available"])

    def test_pending_review_blocks_availability(self):
        tool = self.create_tool()
        self.create_reservation(
            tool,
            date(2026, 8, 10),
            date(2026, 8, 12),
            status="pending_review",
        )

        response = self.availability_request(tool, "2026-08-10", "2026-08-12")

        self.assertFalse(response.get_json()["available"])

    def test_expired_pending_payment_does_not_block_availability(self):
        tool = self.create_tool()
        self.create_reservation(
            tool,
            date(2026, 8, 10),
            date(2026, 8, 12),
            status="pending_payment",
            payment_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        response = self.availability_request(tool, "2026-08-10", "2026-08-12")

        self.assertTrue(response.get_json()["available"])

    def test_expired_reservation_does_not_block_availability(self):
        tool = self.create_tool()
        self.create_reservation(tool, date(2026, 8, 10), date(2026, 8, 12), status="expired")

        response = self.availability_request(tool, "2026-08-10", "2026-08-12")

        self.assertTrue(response.get_json()["available"])

    def test_same_day_range_is_valid(self):
        tool = self.create_tool()

        response = self.availability_request(tool, "2026-08-20", "2026-08-20")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["available"])

    def test_end_date_before_start_date_returns_bad_request(self):
        tool = self.create_tool()

        response = self.availability_request(tool, "2026-08-22", "2026-08-20")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "end_date must be on or after start_date.")

    def test_invalid_or_missing_dates_return_bad_request(self):
        tool = self.create_tool()

        invalid_response = self.availability_request(tool, "20-08-2026", "2026-08-22")
        missing_response = self.client.get(
            f"/api/tools/{tool.id}/availability", query_string={"end_date": "2026-08-22"}
        )

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(missing_response.status_code, 400)

    def test_unpublished_or_missing_tool_returns_not_found(self):
        unpublished_tool = self.create_tool(is_published=False)

        unpublished_response = self.availability_request(unpublished_tool, "2026-08-20", "2026-08-22")
        missing_response = self.client.get(
            "/api/tools/999999/availability",
            query_string={"start_date": "2026-08-20", "end_date": "2026-08-22"},
        )

        self.assertEqual(unpublished_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
