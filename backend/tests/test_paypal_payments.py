import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "paypal-payments-test-secret"
os.environ["PAYPAL_CLIENT_ID"] = "paypal-client-id"
os.environ["PAYPAL_CLIENT_SECRET"] = "paypal-client-secret"
os.environ["PAYPAL_WEBHOOK_ID"] = "paypal-webhook-id"
os.environ["PAYPAL_ENVIRONMENT"] = "sandbox"

from app import create_app
from app.extensions import db
from app.models import Payment, Reservation, Tool
from app.services.payment_domain import (
    PAYMENT_PROVIDER_PAYPAL,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_REQUIRES_REVIEW,
    PAYMENT_WINDOW,
    RESERVATION_STATUS_CANCELLED,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_PENDING_PAYMENT,
)


class PayPalPaymentApiTestCase(unittest.TestCase):
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

    def create_tool(self):
        tool = Tool(name="PayPal tool", category="Tests", daily_price=Decimal("10.00"), deposit_amount=Decimal("25.00"), pickup_available=True, delivery_available=False, is_published=True, is_available=True)
        db.session.add(tool)
        db.session.commit()
        return tool

    def create_reservation(self, tool, **overrides):
        values = {
            "tool_id": tool.id, "start_date": date(2026, 9, 20), "end_date": date(2026, 9, 22),
            "status": RESERVATION_STATUS_PENDING_PAYMENT, "customer_name": "PayPal Customer",
            "customer_email": "paypal-customer@example.com", "customer_phone": "600000000",
            "terms_accepted": True, "privacy_accepted": True, "fulfillment_method": "pickup",
            "payment_expires_at": datetime.now(timezone.utc) + PAYMENT_WINDOW,
            "charged_days": 3, "daily_price_snapshot": Decimal("10.00"), "rental_amount": Decimal("30.00"),
            "delivery_amount": Decimal("0.00"), "total_amount": Decimal("30.00"),
        }
        values.update(overrides)
        reservation = Reservation(**values)
        db.session.add(reservation)
        db.session.commit()
        return reservation

    def create_payment(self, reservation, **overrides):
        values = {
            "reservation_id": reservation.id, "provider": PAYMENT_PROVIDER_PAYPAL,
            "external_payment_id": "PAYPAL-ORDER-1", "status": PAYMENT_STATUS_PENDING,
            "amount": Decimal(reservation.total_amount), "currency": "EUR",
            "idempotency_key": "paypal-payment-idempotency-key", "expires_at": reservation.payment_expires_at,
        }
        values.update(overrides)
        payment = Payment(**values)
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def order(order_id="PAYPAL-ORDER-1"):
        return {"id": order_id, "links": [{"rel": "payer-action", "href": f"https://paypal.test/checkoutnow?token={order_id}"}]}

    @staticmethod
    def event(payment, *, amount="30.00", currency="EUR", event_id="WH-PAYPAL-1"):
        return {
            "id": event_id,
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "status": "COMPLETED", "id": "CAPTURE-1",
                "amount": {"value": amount, "currency_code": currency},
                "supplementary_data": {"related_ids": {"order_id": payment.external_payment_id}},
            },
        }

    def test_creates_order_from_snapshot_amount_in_eur_without_deposit(self):
        tool = self.create_tool()
        reservation = self.create_reservation(tool, total_amount=Decimal("42.75"))
        token_response = MagicMock(); token_response.json.return_value = {"access_token": "token"}; token_response.raise_for_status.return_value = None
        order_response = MagicMock(); order_response.json.return_value = self.order(); order_response.raise_for_status.return_value = None
        with patch("app.services.paypal_checkout.requests.post", side_effect=[token_response, order_response]) as post:
            response = self.client.post(f"/api/reservations/{reservation.id}/payments/paypal")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["approval_url"], self.order()["links"][0]["href"])
        payload = post.call_args_list[1].kwargs["json"]
        self.assertEqual(payload["purchase_units"][0]["amount"], {"currency_code": "EUR", "value": "42.75"})
        self.assertEqual(
            payload["payment_source"]["paypal"]["experience_context"]["return_url"],
            "http://localhost:3000/reserva/confirmada?provider=paypal",
        )
        self.assertNotIn("deposit", str(payload).lower())
        payment = Payment.query.one()
        self.assertEqual(payment.amount, Decimal("42.75"))
        self.assertEqual(payment.currency, "EUR")

    def test_cannot_start_for_missing_expired_or_cancelled_reservation(self):
        tool = self.create_tool()
        expired = self.create_reservation(tool, payment_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        cancelled = self.create_reservation(tool, start_date=date(2026, 10, 1), end_date=date(2026, 10, 3), status=RESERVATION_STATUS_CANCELLED, payment_expires_at=None)
        with patch("app.services.paypal_checkout.requests.post") as post:
            self.assertEqual(self.client.post("/api/reservations/999999/payments/paypal").status_code, 404)
            self.assertEqual(self.client.post(f"/api/reservations/{expired.id}/payments/paypal").status_code, 409)
            self.assertEqual(self.client.post(f"/api/reservations/{cancelled.id}/payments/paypal").status_code, 409)
        post.assert_not_called()

    def test_reuses_existing_order_without_creating_another(self):
        tool = self.create_tool(); reservation = self.create_reservation(tool); self.create_payment(reservation)
        token_response = MagicMock(); token_response.json.return_value = {"access_token": "token"}; token_response.raise_for_status.return_value = None
        order_response = MagicMock(); order_response.json.return_value = self.order(); order_response.raise_for_status.return_value = None
        with patch("app.services.paypal_checkout.requests.post", return_value=token_response) as post, patch("app.services.paypal_checkout.requests.get", return_value=order_response):
            response = self.client.post(f"/api/reservations/{reservation.id}/payments/paypal")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.query.count(), 1)
        self.assertEqual(post.call_count, 1)

    def test_invalid_webhook_is_rejected_before_processing(self):
        with patch("app.routes.payments.verify_paypal_webhook", return_value=False), patch("app.routes.payments.process_paypal_event") as process:
            response = self.client.post("/api/payments/paypal/webhook", json={"id": "event"})
        self.assertEqual(response.status_code, 400)
        process.assert_not_called()

    def test_verified_webhook_confirms_once_and_duplicate_is_safe(self):
        tool = self.create_tool(); reservation = self.create_reservation(tool); payment = self.create_payment(reservation); event = self.event(payment)
        with patch("app.routes.payments.verify_paypal_webhook", return_value=True):
            first = self.client.post("/api/payments/paypal/webhook", json=event)
            second = self.client.post("/api/payments/paypal/webhook", json=event)
        self.assertEqual(first.get_json()["status"], "confirmed")
        self.assertEqual(second.get_json()["status"], "duplicate")
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_CONFIRMED)
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_PAID)

    def test_mismatch_or_late_capture_requires_review_without_confirmation(self):
        tool = self.create_tool(); reservation = self.create_reservation(tool); payment = self.create_payment(reservation)
        with patch("app.routes.payments.verify_paypal_webhook", return_value=True):
            mismatch = self.client.post("/api/payments/paypal/webhook", json=self.event(payment, amount="29.99", currency="USD"))
        self.assertEqual(mismatch.get_json()["status"], "requires_review")
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_REQUIRES_REVIEW)
        db.session.delete(db.session.get(Payment, payment.id)); db.session.commit()
        reservation.payment_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.session.commit()
        late_payment = self.create_payment(reservation, external_payment_id="PAYPAL-ORDER-LATE", idempotency_key="paypal-late")
        with patch("app.routes.payments.verify_paypal_webhook", return_value=True):
            late = self.client.post("/api/payments/paypal/webhook", json=self.event(late_payment, event_id="WH-PAYPAL-LATE"))
        self.assertEqual(late.get_json()["status"], "requires_review")
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_PENDING_PAYMENT)

    def test_browser_capture_does_not_confirm_without_webhook(self):
        tool = self.create_tool(); reservation = self.create_reservation(tool); payment = self.create_payment(reservation)
        token_response = MagicMock(); token_response.json.return_value = {"access_token": "token"}; token_response.raise_for_status.return_value = None
        capture_response = MagicMock(); capture_response.raise_for_status.return_value = None
        with patch("app.services.paypal_checkout.requests.post", side_effect=[token_response, capture_response]):
            response = self.client.post(f"/api/payments/paypal/orders/{payment.external_payment_id}/capture")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_PENDING_PAYMENT)
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_PENDING)

    def test_browser_status_exposes_safe_summary_and_requires_review_without_confirmation(self):
        tool = self.create_tool()
        reservation = self.create_reservation(tool)
        payment = self.create_payment(reservation, status=PAYMENT_STATUS_REQUIRES_REVIEW)

        response = self.client.get(f"/api/payments/paypal/orders/{payment.external_payment_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["payment_status"], PAYMENT_STATUS_REQUIRES_REVIEW)
        self.assertEqual(payload["reservation_status"], RESERVATION_STATUS_PENDING_PAYMENT)
        self.assertEqual(payload["reservation"]["id"], reservation.id)
        self.assertEqual(payload["reservation"]["tool"]["name"], tool.name)
        self.assertNotIn("external_payment_id", payload["reservation"])
