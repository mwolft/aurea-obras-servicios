import os
import unittest
from datetime import date
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "quote-test-secret"

from app import create_app
from app.extensions import db
from app.models import Tool
from app.services.quotes import calculate_quote


class ReservationQuoteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def create_tool(**overrides):
        values = {
            "name": "Quote tool",
            "category": "Demo",
            "daily_price": Decimal("10.00"),
            "deposit_amount": Decimal("50.00"),
            "pickup_available": True,
            "delivery_available": True,
            "delivery_price_per_km": Decimal("1.25"),
            "is_published": True,
            "is_available": True,
        }
        values.update(overrides)
        return Tool(**values)

    def test_inclusive_days_and_pickup_quote(self):
        quote = calculate_quote(
            self.create_tool(), date(2026, 8, 10), date(2026, 8, 12), "pickup"
        )

        self.assertEqual(quote.charged_days, 3)
        self.assertEqual(quote.rental_amount, Decimal("30.00"))
        self.assertEqual(quote.delivery_amount, Decimal("0.00"))
        self.assertEqual(quote.total_amount, Decimal("30.00"))
        self.assertEqual(quote.deposit_amount, Decimal("50.00"))

    def test_same_day_is_one_charged_day(self):
        quote = calculate_quote(
            self.create_tool(), date(2026, 8, 10), date(2026, 8, 10), "pickup"
        )

        self.assertEqual(quote.charged_days, 1)
        self.assertEqual(quote.rental_amount, Decimal("10.00"))

    def test_delivery_quote_uses_total_billable_kilometres_once(self):
        quote = calculate_quote(
            self.create_tool(),
            date(2026, 8, 10),
            date(2026, 8, 12),
            "delivery",
            Decimal("12.50"),
        )

        self.assertEqual(quote.delivery_amount, Decimal("15.63"))
        self.assertEqual(quote.total_amount, Decimal("45.63"))
