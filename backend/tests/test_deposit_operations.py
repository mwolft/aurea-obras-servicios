import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "deposit-operations-test-secret"

from app import create_app
from app.extensions import db
from app.models import EmailOutbox, Payment, Reservation, Tool
from app.models.email_outbox import EMAIL_OUTBOX_STATUS_FAILED, EMAIL_OUTBOX_STATUS_SENT
from app.services.deposit_operations import (
    DEPOSIT_OPERATION_AUTHORIZED_INSUFFICIENT,
    DEPOSIT_OPERATION_AUTHORIZED_SUFFICIENT,
    DEPOSIT_OPERATION_AWAITING_CUSTOMER,
    DEPOSIT_OPERATION_EMAIL_FAILED,
    DEPOSIT_OPERATION_NOT_DUE,
    DEPOSIT_OPERATION_PENDING_REQUEST,
    DEPOSIT_OPERATION_REAUTHORIZE,
    DEPOSIT_OPERATION_REQUEST_EXPIRED,
    evaluate_deposit_operational_state,
    planned_return_cutoff,
    request_due_at,
)
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING_AUTHORIZATION,
)


class DepositOperationsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def reservation(self, *, start=date(2026, 10, 13), end=date(2026, 10, 15)):
        tool = Tool(
            name="Herramienta de prueba",
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=Decimal("100.00"),
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
            status="confirmed",
            customer_name="Cliente",
            customer_email="cliente@example.com",
            customer_phone="600000000",
            fulfillment_method="pickup",
            deposit_amount_snapshot=Decimal("100.00"),
            total_amount=Decimal("30.00"),
        )
        db.session.add(reservation)
        db.session.commit()
        return reservation

    def payment(self, reservation, status, *, expires_at=None, capture_before=None):
        payment = Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=status,
            amount=Decimal("100.00"),
            currency="eur",
            idempotency_key=f"deposit-{reservation.id}-{status}",
            expires_at=expires_at or datetime(2026, 10, 12, 12, tzinfo=timezone.utc),
            capture_before=capture_before,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def now(hour=21):
        return datetime(2026, 10, 10, hour, tzinfo=timezone.utc)

    def test_48_hour_request_window_uses_europe_madrid_start_date(self):
        reservation = self.reservation()
        self.assertEqual(request_due_at(reservation).isoformat(), "2026-10-11T00:00:00+02:00")
        self.assertEqual(
            evaluate_deposit_operational_state(
                reservation, None, None, rental_paid=True, now=self.now(21)
            ).code,
            DEPOSIT_OPERATION_NOT_DUE,
        )
        self.assertEqual(
            evaluate_deposit_operational_state(
                reservation, None, None, rental_paid=True, now=self.now(22)
            ).code,
            DEPOSIT_OPERATION_PENDING_REQUEST,
        )

    def test_pending_email_states_and_expired_checkout_are_distinguished(self):
        reservation = self.reservation()
        payment = self.payment(
            reservation,
            PAYMENT_STATUS_PENDING_AUTHORIZATION,
            expires_at=datetime(2026, 10, 11, 12, tzinfo=timezone.utc),
        )
        sent = EmailOutbox(
            event_type="deposit_authorization_requested",
            reservation_id=reservation.id,
            recipient="cliente@example.com",
            subject="Solicitud",
            text_body="texto",
            html_body="html",
            idempotency_key=f"deposit:{payment.id}:authorization_requested",
            status=EMAIL_OUTBOX_STATUS_SENT,
        )
        db.session.add(sent)
        db.session.commit()
        self.assertEqual(
            evaluate_deposit_operational_state(
                reservation, payment, sent, rental_paid=True, now=self.now(22)
            ).code,
            DEPOSIT_OPERATION_AWAITING_CUSTOMER,
        )
        sent.status = EMAIL_OUTBOX_STATUS_FAILED
        db.session.commit()
        self.assertEqual(
            evaluate_deposit_operational_state(
                reservation, payment, sent, rental_paid=True, now=self.now(22)
            ).code,
            DEPOSIT_OPERATION_EMAIL_FAILED,
        )
        payment.expires_at = datetime(2026, 10, 10, 21, tzinfo=timezone.utc)
        db.session.commit()
        self.assertEqual(
            evaluate_deposit_operational_state(
                reservation, payment, sent, rental_paid=True, now=self.now(22)
            ).code,
            DEPOSIT_OPERATION_REQUEST_EXPIRED,
        )

    def test_capture_before_is_the_authority_for_coverage_and_long_rental_warning(self):
        reservation = self.reservation(start=date(2026, 10, 13), end=date(2026, 10, 18))
        required_until = planned_return_cutoff(reservation) + timedelta(hours=24)
        payment = self.payment(
            reservation,
            PAYMENT_STATUS_AUTHORIZED,
            capture_before=required_until.astimezone(timezone.utc) + timedelta(minutes=1),
        )
        state = evaluate_deposit_operational_state(
            reservation, payment, None, rental_paid=True, now=self.now(22)
        )
        self.assertEqual(state.code, DEPOSIT_OPERATION_AUTHORIZED_SUFFICIENT)
        self.assertTrue(state.long_rental)
        self.assertTrue(state.coverage_sufficient)

        payment.capture_before = required_until.astimezone(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
        state = evaluate_deposit_operational_state(
            reservation, payment, None, rental_paid=True, now=self.now(22)
        )
        self.assertEqual(state.code, DEPOSIT_OPERATION_AUTHORIZED_INSUFFICIENT)
        self.assertFalse(state.coverage_sufficient)

    def test_expired_authorization_requires_reauthorization_before_delivery(self):
        reservation = self.reservation()
        payment = self.payment(
            reservation,
            PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
        )
        self.assertEqual(
            evaluate_deposit_operational_state(
                reservation, payment, None, rental_paid=True, now=self.now(22)
            ).code,
            DEPOSIT_OPERATION_REAUTHORIZE,
        )

    def test_unpaid_rental_is_not_an_operational_deposit_request(self):
        reservation = self.reservation()
        state = evaluate_deposit_operational_state(
            reservation, None, None, rental_paid=False, now=self.now(22)
        )
        self.assertEqual(state.code, "not_applicable")
