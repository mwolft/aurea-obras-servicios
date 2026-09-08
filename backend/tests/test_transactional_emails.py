import os
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "transactional-email-test-secret"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_transactional_email"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_transactional_email"

from app import create_app
from app.extensions import db
from app.models import EmailOutbox, Payment, Reservation, Tool
from app.models.email_outbox import EMAIL_OUTBOX_STATUS_FAILED, EMAIL_OUTBOX_STATUS_SENT
from app.services.deposit_authorizations import (
    capture_deposit_authorization,
    process_stripe_deposit_event,
    release_deposit_authorization,
)
from app.services.email.outbox import (
    deliver_outbox_email,
    queue_transactional_email,
    retry_failed_outbox_email,
)
from app.services.email.resend import ResendDeliveryError
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_PENDING_AUTHORIZATION,
    PAYMENT_WINDOW,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_PENDING_PAYMENT,
)
from app.services.rental_lifecycle import (
    complete_reservation_rental,
    mark_reservation_delivered,
    mark_reservation_returned,
)
from app.services.reservations import cancel_reservation
from app.services.stripe_checkout import process_stripe_event
from app.services.email.base import EmailContent


class TransactionalEmailTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(
            RESEND_API_KEY="test-resend-secret",
            CONTACT_FROM_EMAIL="AUREA <contact@example.test>",
            CONTACT_TO_EMAIL="operations@example.test",
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def tool(self, deposit=Decimal("0.00")):
        tool = Tool(
            name=f"Herramienta {uuid.uuid4().hex[:8]}",
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=deposit,
            pickup_available=True,
            delivery_available=False,
            is_published=True,
            is_available=True,
        )
        db.session.add(tool)
        db.session.commit()
        return tool

    def reservation(self, tool, *, status=RESERVATION_STATUS_PENDING_PAYMENT):
        reservation = Reservation(
            tool_id=tool.id,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            status=status,
            customer_name="Cliente <prueba>",
            customer_email="cliente@example.test",
            customer_phone="600000000",
            terms_accepted=True,
            privacy_accepted=True,
            fulfillment_method="pickup",
            payment_expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW,
            daily_price_snapshot=Decimal("10.00"),
            charged_days=2,
            rental_amount=Decimal("20.00"),
            delivery_amount=Decimal("0.00"),
            total_amount=Decimal("20.00"),
            deposit_amount_snapshot=Decimal(tool.deposit_amount),
        )
        db.session.add(reservation)
        db.session.commit()
        return reservation

    def rental_payment(self, reservation):
        payment = Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
            external_payment_id=f"cs_{reservation.id}",
            status=PAYMENT_STATUS_PENDING,
            amount=Decimal(reservation.total_amount),
            currency="eur",
            idempotency_key=uuid.uuid4().hex,
            expires_at=reservation.payment_expires_at,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def checkout_event(payment, event_id="evt_confirmed"):
        return {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": payment.external_payment_id,
                "payment_status": "paid",
                "amount_total": 2000,
                "currency": "eur",
                "client_reference_id": str(payment.id),
                "metadata": {"payment_id": str(payment.id)},
            }},
        }

    def deposit_payment(self, reservation, *, status=PAYMENT_STATUS_PENDING_AUTHORIZATION):
        payment = Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=status,
            amount=Decimal(reservation.deposit_amount_snapshot),
            currency="eur",
            idempotency_key=uuid.uuid4().hex,
            expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def deposit_event(payment, event_type="payment_intent.amount_capturable_updated", event_id="evt_deposit"):
        return {
            "id": event_id,
            "type": event_type,
            "data": {"object": {
                "id": f"pi_{payment.id}",
                "status": "requires_capture",
                "amount_capturable": int(Decimal(payment.amount) * 100),
                "amount_received": 0,
                "metadata": {"payment_id": str(payment.id), "purpose": PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION},
                "latest_charge": {"id": f"ch_{payment.id}", "payment_method_details": {"card": {"capture_before": 1_900_000_000}}},
            }},
        }

    def test_confirmed_payment_queues_one_escaped_customer_email_and_duplicate_does_not_repeat(self):
        reservation = self.reservation(self.tool())
        payment = self.rental_payment(reservation)
        outbox_ids = []
        event = self.checkout_event(payment)
        db.session.rollback()
        self.assertEqual(process_stripe_event(event, outbox_ids=outbox_ids), "confirmed")
        self.assertEqual(process_stripe_event(event, outbox_ids=outbox_ids), "duplicate")
        self.assertEqual(EmailOutbox.query.count(), 1)
        email = EmailOutbox.query.one()
        self.assertEqual(outbox_ids, [email.id])
        self.assertEqual(email.event_type, "reservation_confirmed")
        self.assertIn("Cliente &lt;prueba&gt;", email.html_body)
        self.assertNotIn(payment.external_payment_id, email.html_body)
        self.assertNotIn(payment.external_payment_id, email.text_body)

    def test_cancel_delivery_return_and_completion_each_queue_one_customer_email(self):
        cancelled = self.reservation(self.tool())
        cancelled_id = cancelled.id
        ids = []
        db.session.rollback()
        cancel_reservation(cancelled_id, outbox_ids=ids)
        self.assertEqual(EmailOutbox.query.filter_by(event_type="reservation_cancelled").count(), 1)

        active = self.reservation(self.tool(), status=RESERVATION_STATUS_CONFIRMED)
        active_id = active.id
        db.session.rollback()
        mark_reservation_delivered(active_id, outbox_ids=ids)
        mark_reservation_returned(active_id, outbox_ids=ids)
        complete_reservation_rental(active_id, outbox_ids=ids)
        events = {item.event_type for item in EmailOutbox.query.all()}
        self.assertTrue({"reservation_delivered", "reservation_returned", "reservation_completed"}.issubset(events))

    def test_deposit_authorization_release_and_capture_queue_customer_emails_without_internal_reason(self):
        reservation = self.reservation(self.tool(Decimal("100.00")), status=RESERVATION_STATUS_CONFIRMED)
        payment = self.deposit_payment(reservation)
        reservation_id = reservation.id
        event = self.deposit_event(payment)
        ids = []
        db.session.rollback()
        self.assertEqual(process_stripe_deposit_event(event, outbox_ids=ids), "authorized")
        with patch("app.services.deposit_authorizations.stripe.PaymentIntent.cancel"):
            release_deposit_authorization(reservation_id, outbox_ids=ids)
        released = EmailOutbox.query.filter_by(event_type="deposit_released").one()
        self.assertIn("Fianza liberada", released.subject)

        second = self.reservation(self.tool(Decimal("100.00")), status=RESERVATION_STATUS_CONFIRMED)
        second_id = second.id
        deposit = self.deposit_payment(second, status=PAYMENT_STATUS_AUTHORIZED)
        deposit.authorized_amount = Decimal("100.00")
        deposit.external_payment_id = "pi_capture"
        deposit.capture_before = datetime.now(timezone.utc) + timedelta(days=1)
        db.session.commit()
        intent = {"status": "succeeded", "amount_received": 4000, "latest_charge": "ch_capture"}
        with patch("app.services.deposit_authorizations.stripe.PaymentIntent.capture", return_value=intent):
            capture_deposit_authorization(second_id, Decimal("40.00"), "Nota interna privada", outbox_ids=ids)
        captured = EmailOutbox.query.filter_by(event_type="deposit_captured").one()
        self.assertIn("40.00 €", captured.html_body)
        self.assertNotIn("Nota interna privada", captured.html_body)
        self.assertNotIn("Nota interna privada", captured.text_body)

    def test_deposit_failure_and_financial_review_queue_only_internal_alerts(self):
        reservation = self.reservation(self.tool(Decimal("100.00")), status=RESERVATION_STATUS_CONFIRMED)
        payment = self.deposit_payment(reservation)
        ids = []
        failed = self.deposit_event(payment, event_type="payment_intent.payment_failed", event_id="evt_failed")
        db.session.rollback()
        self.assertEqual(process_stripe_deposit_event(failed, outbox_ids=ids), "authorization_failed")
        email = EmailOutbox.query.one()
        self.assertEqual(email.recipient, "operations@example.test")
        self.assertEqual(email.event_type, "deposit_authorization_failed")

    def test_failed_resend_delivery_does_not_rollback_and_manual_retry_sends_once(self):
        reservation = self.reservation(self.tool())
        reservation_id = reservation.id
        ids = []
        db.session.rollback()
        cancel_reservation(reservation_id, outbox_ids=ids)
        email_id = ids[0]
        with patch("app.services.email.outbox.send_resend_email", side_effect=ResendDeliveryError("x")):
            self.assertFalse(deliver_outbox_email(email_id))
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "cancelled")
        failed = db.session.get(EmailOutbox, email_id)
        self.assertEqual(failed.status, EMAIL_OUTBOX_STATUS_FAILED)
        with patch("app.services.email.outbox.send_resend_email", return_value="re_test_1") as send:
            self.assertTrue(retry_failed_outbox_email(email_id))
            self.assertFalse(retry_failed_outbox_email(email_id))
        self.assertEqual(db.session.get(EmailOutbox, email_id).status, EMAIL_OUTBOX_STATUS_SENT)
        send.assert_called_once()

    def test_review_required_alert_is_queued_once_without_provider_references(self):
        reservation = self.reservation(self.tool())
        payment = self.rental_payment(reservation)
        ids = []
        event = self.checkout_event(payment, event_id="evt_review")
        event["data"]["object"]["amount_total"] = 1999
        db.session.rollback()
        self.assertEqual(process_stripe_event(event, outbox_ids=ids), "requires_review")
        email = EmailOutbox.query.one()
        self.assertEqual(email.event_type, "financial_review_required")
        self.assertNotIn(payment.external_payment_id, email.html_body)

    def test_outbox_keeps_content_for_retry(self):
        reservation = self.reservation(self.tool())
        reservation_id = reservation.id
        db.session.rollback()
        with db.session.begin():
            email = queue_transactional_email(
                db.session,
                event_type="test",
                idempotency_key="test:outbox:content",
                recipient="cliente@example.test",
                subject="Prueba",
                content=EmailContent(text="Texto", html="<p>Texto</p>"),
                reservation_id=reservation_id,
            )
        self.assertEqual(email.text_body, "Texto")
        self.assertEqual(email.html_body, "<p>Texto</p>")


if __name__ == "__main__":
    unittest.main()
