import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "deposit-request-automation-test-secret"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_deposit_automation"

from app import create_app
from app.extensions import db
from app.models import EmailOutbox, Payment, Reservation, Tool
from app.services.admin_dashboard import get_dashboard_summary
from app.services.deposit_request_automation import request_due_deposit_authorizations
from app.services.email.rental import EVENT_DEPOSIT_AUTOMATION_FAILED
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING_AUTHORIZATION,
    PAYMENT_STATUS_REQUIRES_REVIEW,
)
from app.services.stripe_checkout import StripeCheckoutError


class DepositRequestAutomationTestCase(unittest.TestCase):
    due_now = datetime(2026, 10, 10, 22, tzinfo=timezone.utc)

    def setUp(self):
        self.app = create_app()
        self.app.config["CONTACT_TO_EMAIL"] = "admin@example.com"
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def reservation(self, *, start=date(2026, 10, 13), end=date(2026, 10, 14), status="confirmed", deposit=Decimal("100.00")):
        tool = Tool(
            name="Herramienta automática",
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=deposit,
            pickup_available=True,
            delivery_available=False,
            is_published=True,
            is_available=True,
        )
        db.session.add(tool)
        db.session.flush()
        reservation = Reservation(
            tool_id=tool.id,
            start_date=start,
            end_date=end,
            status=status,
            customer_name="Cliente automático",
            customer_email="cliente@example.com",
            customer_phone="600000000",
            fulfillment_method="pickup",
            terms_accepted=True if status == "pending_payment" else None,
            privacy_accepted=True if status == "pending_payment" else None,
            payment_expires_at=(
                self.due_now + timedelta(minutes=30)
                if status == "pending_payment" else None
            ),
            total_amount=Decimal("20.00"),
            deposit_amount_snapshot=deposit,
        )
        db.session.add(reservation)
        db.session.flush()
        db.session.add(Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
            status=PAYMENT_STATUS_PAID,
            amount=Decimal("20.00"),
            currency="eur",
            idempotency_key=f"rental-{reservation.id}",
            expires_at=self.due_now + timedelta(minutes=30),
        ))
        db.session.commit()
        return reservation

    @staticmethod
    def checkout(checkout_id="cs_automation"):
        checkout = MagicMock()
        checkout.id = checkout_id
        checkout.url = f"https://checkout.stripe.test/c/pay/{checkout_id}"
        checkout.status = "open"
        return checkout

    def deposit(self, reservation, status, **values):
        payment = Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=status,
            amount=reservation.deposit_amount_snapshot,
            currency="eur",
            idempotency_key=f"deposit-{reservation.id}-{status}",
            expires_at=values.pop("expires_at", self.due_now + timedelta(hours=24)),
            **values,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    def run_with_checkout(self, checkout_id="cs_automation"):
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=self.checkout(checkout_id),
        ) as create, patch(
            "app.services.email.outbox.send_resend_email", return_value="re_automation"
        ):
            result = request_due_deposit_authorizations(now=self.due_now)
        return result, create

    def test_more_than_48_hours_does_not_request(self):
        self.reservation(start=date(2026, 10, 14), end=date(2026, 10, 15))
        result, create = self.run_with_checkout()
        self.assertEqual((result.requested, result.skipped, result.failed), (0, 1, 0))
        create.assert_not_called()
        self.assertEqual(Payment.query.filter_by(purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION).count(), 0)

    def test_due_reservation_requests_once_and_repeat_is_idempotent(self):
        reservation = self.reservation()
        result, create = self.run_with_checkout()
        self.assertEqual((result.requested, result.failed), (1, 0))
        create.assert_called_once()
        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation.id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            1,
        )
        self.assertEqual(EmailOutbox.query.filter_by(reservation_id=reservation.id).count(), 1)

        result, repeated_create = self.run_with_checkout("cs_should_not_exist")
        self.assertEqual((result.requested, result.skipped, result.failed), (0, 1, 0))
        repeated_create.assert_not_called()
        self.assertEqual(EmailOutbox.query.filter_by(reservation_id=reservation.id).count(), 1)

    def test_reservation_confirmed_inside_window_is_requested_immediately(self):
        reservation = self.reservation(start=date(2026, 10, 11), end=date(2026, 10, 11))
        result, create = self.run_with_checkout()
        self.assertEqual(result.requested, 1)
        create.assert_called_once()
        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation.id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            1,
        )

    def test_past_confirmed_reservation_is_not_requested_automatically(self):
        self.reservation(start=date(2026, 10, 9), end=date(2026, 10, 9))
        result, create = self.run_with_checkout()
        self.assertEqual((result.requested, result.skipped, result.failed), (0, 1, 0))
        create.assert_not_called()

    def test_manual_or_active_request_is_never_duplicated(self):
        reservation = self.reservation()
        deposit = self.deposit(
            reservation,
            PAYMENT_STATUS_PENDING_AUTHORIZATION,
            provider_checkout_id="cs_manual_request",
        )
        db.session.add(EmailOutbox(
            event_type="deposit_authorization_requested",
            reservation_id=reservation.id,
            recipient="cliente@example.com",
            subject="Solicitud",
            text_body="Texto",
            html_body="<p>Texto</p>",
            idempotency_key=f"deposit:{deposit.id}:authorization_requested",
            status="sent",
        ))
        db.session.commit()
        result, create = self.run_with_checkout()
        self.assertEqual((result.requested, result.skipped), (0, 1))
        create.assert_not_called()

    def test_authorized_review_and_incompatible_reservations_are_skipped(self):
        authorized = self.reservation()
        self.deposit(
            authorized,
            PAYMENT_STATUS_AUTHORIZED,
            external_payment_id="pi_authorized",
            capture_before=self.due_now + timedelta(days=3),
        )
        reviewed = self.reservation()
        self.deposit(reviewed, PAYMENT_STATUS_REQUIRES_REVIEW)
        zero = self.reservation(deposit=Decimal("0.00"))
        unpaid = self.reservation()
        Payment.query.filter_by(
            reservation_id=unpaid.id,
            purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
        ).one().status = "pending"
        unconfirmed = self.reservation(status="pending_payment")
        db.session.commit()

        result, create = self.run_with_checkout()
        self.assertEqual((result.requested, result.scanned), (0, 3))
        create.assert_not_called()
        self.assertEqual(
            Payment.query.filter_by(purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION).count(), 2
        )

    def test_email_failure_keeps_the_checkout_and_is_not_repeated_automatically(self):
        reservation = self.reservation()
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=self.checkout("cs_email_failure"),
        ) as create, patch(
            "app.services.email.outbox.send_resend_email",
            side_effect=RuntimeError("Resend unavailable"),
        ):
            first = request_due_deposit_authorizations(now=self.due_now)
        self.assertEqual(first.requested, 1)
        self.assertEqual(EmailOutbox.query.filter_by(reservation_id=reservation.id).one().status, "failed")
        second, repeated_create = self.run_with_checkout()
        self.assertEqual((second.requested, second.skipped), (0, 1))
        create.assert_called_once()
        repeated_create.assert_not_called()
        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation.id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            1,
        )

    def test_long_rental_does_not_trigger_a_second_authorization_when_already_active(self):
        reservation = self.reservation(start=date(2026, 10, 11), end=date(2026, 10, 16))
        self.deposit(
            reservation,
            PAYMENT_STATUS_AUTHORIZED,
            external_payment_id="pi_long_rental",
            capture_before=self.due_now + timedelta(days=7),
        )
        result, create = self.run_with_checkout()
        self.assertEqual((result.requested, result.skipped), (0, 1))
        create.assert_not_called()

    def test_stripe_failure_is_persisted_as_dashboard_attention_without_changing_reservation(self):
        reservation = self.reservation()
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            side_effect=StripeCheckoutError("Stripe unavailable"),
        ), patch(
            "app.services.email.outbox.send_resend_email", return_value="re_failure"
        ):
            result = request_due_deposit_authorizations(now=self.due_now)

        self.assertEqual(result.failed, 1)
        self.assertEqual(db.session.get(Reservation, reservation.id).status, "confirmed")
        alert = EmailOutbox.query.filter_by(
            reservation_id=reservation.id,
            event_type=EVENT_DEPOSIT_AUTOMATION_FAILED,
        ).one()
        self.assertEqual(alert.status, "sent")
        dashboard = get_dashboard_summary(today=date(2026, 10, 10))
        self.assertEqual([item.reservation_id for item in dashboard.deposit_attention], [reservation.id])

    def test_hourly_cli_command_is_safe_when_nothing_is_due(self):
        result = self.app.test_cli_runner().invoke(args=["request-due-deposits"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("0 creadas", result.output)
