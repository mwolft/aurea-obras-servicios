import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "stripe-payments-test-secret"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_unit_test"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_unit_test"

from app import create_app
from app.extensions import db
from app.models import Payment, Reservation, Tool, User
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_REQUIRES_REVIEW,
    PAYMENT_WINDOW,
    RESERVATION_STATUS_CANCELLED,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_PENDING_PAYMENT,
)


class StripePaymentApiTestCase(unittest.TestCase):
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

    def create_tool(self) -> Tool:
        tool = Tool(
            name="Payment tool",
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
        return tool

    def create_reservation(self, tool: Tool, **overrides) -> Reservation:
        values = {
            "tool_id": tool.id,
            "start_date": date(2026, 9, 20),
            "end_date": date(2026, 9, 22),
            "status": RESERVATION_STATUS_PENDING_PAYMENT,
            "customer_name": "Stripe Customer",
            "customer_email": "stripe-customer@example.com",
            "customer_phone": "600000000",
            "terms_accepted": True,
            "privacy_accepted": True,
            "fulfillment_method": "pickup",
            "payment_expires_at": datetime.now(timezone.utc) + PAYMENT_WINDOW,
            "charged_days": 3,
            "daily_price_snapshot": Decimal("10.00"),
            "rental_amount": Decimal("30.00"),
            "delivery_amount": Decimal("0.00"),
            "total_amount": Decimal("30.00"),
        }
        values.update(overrides)
        reservation = Reservation(**values)
        db.session.add(reservation)
        db.session.commit()
        return reservation

    def create_payment(self, reservation: Reservation, **overrides) -> Payment:
        values = {
            "reservation_id": reservation.id,
            "provider": PAYMENT_PROVIDER_STRIPE,
            "external_payment_id": "cs_test_payment",
            "status": PAYMENT_STATUS_PENDING,
            "amount": Decimal(reservation.total_amount),
            "currency": "eur",
            "idempotency_key": "test-payment-idempotency-key",
            "expires_at": reservation.payment_expires_at,
        }
        values.update(overrides)
        payment = Payment(**values)
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def checkout_session(session_id: str = "cs_test_created") -> MagicMock:
        session = MagicMock()
        session.id = session_id
        session.url = f"https://checkout.stripe.test/c/pay/{session_id}"
        return session

    @staticmethod
    def stripe_event(payment: Payment, *, amount_total: int = 3000, currency: str = "eur", event_id: str = "evt_test_paid") -> dict:
        return {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": payment.external_payment_id,
                    "payment_status": "paid",
                    "amount_total": amount_total,
                    "currency": currency,
                    "client_reference_id": str(payment.id),
                    "metadata": {"payment_id": str(payment.id)},
                }
            },
        }

    def test_starts_checkout_from_the_persisted_reservation_total(self):
        tool = self.create_tool()
        reservation = self.create_reservation(tool, total_amount=Decimal("42.75"))
        checkout = self.checkout_session()

        with patch(
            "app.services.stripe_checkout.stripe.checkout.Session.create",
            return_value=checkout,
        ) as create_session:
            response = self.client.post(f"/api/reservations/{reservation.id}/payments/stripe")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["checkout_url"], checkout.url)
        self.assertEqual(create_session.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"], 4275)
        self.assertEqual(create_session.call_args.kwargs["line_items"][0]["price_data"]["currency"], "eur")
        self.assertNotIn("deposit", str(create_session.call_args.kwargs))
        payment = Payment.query.one()
        self.assertEqual(payment.amount, Decimal("42.75"))
        self.assertEqual(payment.currency, "eur")
        self.assertEqual(payment.status, PAYMENT_STATUS_PENDING)
        payment_expiration = payment.expires_at
        if payment_expiration.tzinfo is None:
            payment_expiration = payment_expiration.replace(tzinfo=timezone.utc)
        self.assertAlmostEqual(
            (payment_expiration - datetime.now(timezone.utc)).total_seconds(),
            PAYMENT_WINDOW.total_seconds(),
            delta=5,
        )

    def test_cannot_start_checkout_for_a_missing_expired_or_cancelled_reservation(self):
        tool = self.create_tool()
        expired = self.create_reservation(
            tool, payment_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        cancelled = self.create_reservation(
            tool,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 3),
            status=RESERVATION_STATUS_CANCELLED,
            payment_expires_at=None,
        )

        with patch("app.services.stripe_checkout.stripe.checkout.Session.create") as create_session:
            missing_response = self.client.post("/api/reservations/999999/payments/stripe")
            expired_response = self.client.post(f"/api/reservations/{expired.id}/payments/stripe")
            cancelled_response = self.client.post(f"/api/reservations/{cancelled.id}/payments/stripe")

        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(expired_response.status_code, 409)
        self.assertEqual(cancelled_response.status_code, 409)
        create_session.assert_not_called()

    def test_second_checkout_start_reuses_the_same_session(self):
        tool = self.create_tool()
        reservation = self.create_reservation(tool)
        checkout = self.checkout_session()

        with patch(
            "app.services.stripe_checkout.stripe.checkout.Session.create",
            return_value=checkout,
        ) as create_session, patch(
            "app.services.stripe_checkout.stripe.checkout.Session.retrieve",
            return_value=checkout,
        ) as retrieve_session:
            first = self.client.post(f"/api/reservations/{reservation.id}/payments/stripe")
            second = self.client.post(f"/api/reservations/{reservation.id}/payments/stripe")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        create_session.assert_called_once()
        retrieve_session.assert_called_once_with("cs_test_created")
        self.assertEqual(Payment.query.count(), 1)

    def test_invalid_webhook_signature_is_rejected(self):
        with patch("app.routes.payments.construct_stripe_event", side_effect=ValueError):
            response = self.client.post("/api/payments/stripe/webhook", data=b"{}")

        self.assertEqual(response.status_code, 400)

    def test_verified_payment_webhook_confirms_once_and_ignores_a_duplicate(self):
        tool = self.create_tool()
        reservation = self.create_reservation(tool)
        payment = self.create_payment(reservation)
        event = self.stripe_event(payment)

        with patch("app.routes.payments.construct_stripe_event", return_value=event):
            first = self.client.post("/api/payments/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "test"})
            second = self.client.post("/api/payments/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "test"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["status"], "confirmed")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()["status"], "duplicate")
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_CONFIRMED)
        persisted_payment = db.session.get(Payment, payment.id)
        self.assertEqual(persisted_payment.status, PAYMENT_STATUS_PAID)
        self.assertEqual(persisted_payment.provider_event_id, "evt_test_paid")

    def test_mismatched_amount_or_currency_never_confirms_the_reservation(self):
        tool = self.create_tool()
        reservation = self.create_reservation(tool)
        payment = self.create_payment(reservation)
        event = self.stripe_event(payment, amount_total=2999, currency="usd")

        with patch("app.routes.payments.construct_stripe_event", return_value=event):
            response = self.client.post("/api/payments/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "test"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "requires_review")
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_PENDING_PAYMENT)
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_REQUIRES_REVIEW)

    def test_late_payment_webhook_does_not_confirm_an_expired_reservation(self):
        tool = self.create_tool()
        reservation = self.create_reservation(
            tool, payment_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        payment = self.create_payment(reservation)
        event = self.stripe_event(payment)

        with patch("app.routes.payments.construct_stripe_event", return_value=event):
            response = self.client.post("/api/payments/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "test"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "requires_review")
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_PENDING_PAYMENT)
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_REQUIRES_REVIEW)

    def test_browser_status_check_without_a_webhook_never_confirms(self):
        tool = self.create_tool()
        reservation = self.create_reservation(tool)
        payment = self.create_payment(reservation)

        response = self.client.get(f"/api/payments/stripe/sessions/{payment.external_payment_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["payment_status"], PAYMENT_STATUS_PENDING)
        self.assertEqual(response.get_json()["reservation_status"], RESERVATION_STATUS_PENDING_PAYMENT)
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_PENDING_PAYMENT)

    def test_owned_reservation_cannot_be_paid_from_another_session(self):
        tool = self.create_tool()
        owner = User(name="Owner", email="owner@example.com", password_hash="unused")
        other_user = User(name="Other", email="other@example.com", password_hash="unused")
        db.session.add_all([owner, other_user])
        db.session.commit()
        reservation = self.create_reservation(tool, user_id=owner.id)
        with self.client.session_transaction() as session:
            session["user_id"] = other_user.id

        with patch("app.services.stripe_checkout.stripe.checkout.Session.create") as create_session:
            response = self.client.post(f"/api/reservations/{reservation.id}/payments/stripe")

        self.assertEqual(response.status_code, 404)
        create_session.assert_not_called()
