import os
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

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
    start_or_recover_deposit_checkout,
)
from app.services.email.outbox import (
    deliver_outbox_email,
    queue_transactional_email,
    retry_failed_outbox_email,
)
from app.services.email.resend import ResendDeliveryError
from app.services.payment_domain import (
    PAYMENT_PROVIDER_PAYPAL,
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
    RESERVATION_STATUS_RETURNED_PENDING_CLOSURE,
)
from app.services.rental_lifecycle import (
    complete_reservation_rental,
    mark_reservation_delivered,
    mark_reservation_returned,
)
from app.services.reservations import cancel_reservation
from app.services.reservations import create_reservation, review_delivery_reservation
from app.services.email.rental import (
    EVENT_DEPOSIT_AUTHORIZED,
    EVENT_DEPOSIT_AUTHORIZED_INTERNAL,
    EVENT_RESERVATION_CONFIRMED,
    EVENT_RESERVATION_CONFIRMED_INTERNAL,
    queue_delivery_review_requested,
)
from app.services.paypal_checkout import process_paypal_event
from app.services.stripe_checkout import process_stripe_event
from app.services.email.base import EmailContent


class TransactionalEmailTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(
            RESEND_API_KEY="test-resend-secret",
            CONTACT_FROM_EMAIL="AUREA <contact@example.test>",
            CONTACT_TO_EMAIL="operations@example.test",
            BACKEND_ORIGIN="https://api.example.test",
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def tool(self, deposit=Decimal("0.00"), *, delivery_available=False):
        tool = Tool(
            name=f"Herramienta {uuid.uuid4().hex[:8]}",
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=deposit,
            pickup_available=True,
            delivery_available=delivery_available,
            delivery_price_per_km=Decimal("1.50") if delivery_available else None,
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

    def rental_payment(self, reservation, *, provider=PAYMENT_PROVIDER_STRIPE):
        external_payment_id = (
            f"cs_{reservation.id}"
            if provider == PAYMENT_PROVIDER_STRIPE
            else f"paypal_order_{reservation.id}"
        )
        payment = Payment(
            reservation_id=reservation.id,
            provider=provider,
            purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
            external_payment_id=external_payment_id,
            status=PAYMENT_STATUS_PENDING,
            amount=Decimal(reservation.total_amount),
            currency="EUR" if provider == PAYMENT_PROVIDER_PAYPAL else "eur",
            idempotency_key=uuid.uuid4().hex,
            expires_at=reservation.payment_expires_at,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def checkout_event(payment, event_id="evt_confirmed", *, amount_total=None):
        return {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": payment.external_payment_id,
                "payment_status": "paid",
                "amount_total": int(Decimal(payment.amount) * 100) if amount_total is None else amount_total,
                "currency": "eur",
                "client_reference_id": str(payment.id),
                "metadata": {"payment_id": str(payment.id)},
            }},
        }

    @staticmethod
    def paypal_event(payment, event_id="WH-confirmed"):
        return {
            "id": event_id,
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "status": "COMPLETED",
                "amount": {"value": str(payment.amount), "currency_code": "EUR"},
                "supplementary_data": {"related_ids": {"order_id": payment.external_payment_id}},
            },
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

    def test_confirmed_pickup_payment_queues_customer_and_internal_emails_once(self):
        reservation = self.reservation(self.tool())
        payment = self.rental_payment(reservation)
        outbox_ids = []
        event = self.checkout_event(payment)
        db.session.rollback()
        self.assertEqual(process_stripe_event(event, outbox_ids=outbox_ids), "confirmed")
        self.assertEqual(process_stripe_event(event, outbox_ids=outbox_ids), "duplicate")
        self.assertEqual(EmailOutbox.query.count(), 2)
        customer_email = EmailOutbox.query.filter_by(event_type=EVENT_RESERVATION_CONFIRMED).one()
        internal_email = EmailOutbox.query.filter_by(
            event_type=EVENT_RESERVATION_CONFIRMED_INTERNAL
        ).one()
        self.assertEqual(set(outbox_ids), {customer_email.id, internal_email.id})
        self.assertEqual(customer_email.recipient, "cliente@example.test")
        self.assertEqual(internal_email.recipient, "operations@example.test")
        self.assertIn("Cliente &lt;prueba&gt;", customer_email.html_body)
        self.assertIn("Recogida en almacén", internal_email.html_body)
        self.assertIn("20.00 €", internal_email.html_body)
        self.assertIn("Gestionar reserva", internal_email.html_body)
        self.assertNotIn(payment.external_payment_id, internal_email.html_body)
        self.assertNotIn(payment.external_payment_id, internal_email.text_body)

    def test_confirmed_delivery_payment_includes_confirmed_transport_snapshots_for_aurea(self):
        tool_id = self.tool(Decimal("100.00"), delivery_available=True).id
        db.session.rollback()
        reservation = create_reservation(
            tool_id,
            date(2026, 10, 1),
            date(2026, 10, 2),
            "Cliente transporte",
            "cliente@example.test",
            "600000000",
            True,
            True,
            "delivery",
            "Calle de entrega 1",
        )
        reservation_id = reservation.id
        db.session.rollback()
        review_delivery_reservation(reservation_id, Decimal("12.50"))
        reservation = db.session.get(Reservation, reservation_id)
        payment = self.rental_payment(reservation)
        outbox_ids = []
        event = self.checkout_event(payment, event_id="evt_delivery_confirmed")
        db.session.rollback()

        self.assertEqual(process_stripe_event(event, outbox_ids=outbox_ids), "confirmed")
        self.assertEqual(process_stripe_event(event, outbox_ids=outbox_ids), "duplicate")

        internal_email = EmailOutbox.query.filter_by(
            event_type=EVENT_RESERVATION_CONFIRMED_INTERNAL,
            reservation_id=reservation_id,
        ).one()
        admin_url = f"https://api.example.test/admin/reservation/details/?id={reservation_id}"
        self.assertIn("Modalidad", internal_email.html_body)
        self.assertIn("Entrega", internal_email.html_body)
        self.assertIn("Calle de entrega 1", internal_email.html_body)
        self.assertIn("12.50 km", internal_email.html_body)
        self.assertIn("1.50 €/km", internal_email.html_body)
        self.assertIn("18.75 €", internal_email.html_body)
        self.assertIn("38.75 €", internal_email.html_body)
        self.assertIn("100.00 €", internal_email.html_body)
        self.assertIn("Gestionar reserva", internal_email.html_body)
        self.assertIn(admin_url, internal_email.html_body)
        self.assertIn(admin_url, internal_email.text_body)
        self.assertEqual(
            EmailOutbox.query.filter_by(
                event_type=EVENT_RESERVATION_CONFIRMED_INTERNAL,
                reservation_id=reservation_id,
            ).count(),
            1,
        )

    def test_paypal_confirmation_queues_the_same_customer_and_internal_email_events(self):
        reservation = self.reservation(self.tool())
        payment = self.rental_payment(reservation, provider=PAYMENT_PROVIDER_PAYPAL)
        outbox_ids = []
        event = self.paypal_event(payment)
        db.session.rollback()

        self.assertEqual(process_paypal_event(event, outbox_ids=outbox_ids), "confirmed")
        self.assertEqual(process_paypal_event(event, outbox_ids=outbox_ids), "duplicate")
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_CONFIRMED)
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_PAID)
        self.assertEqual(
            EmailOutbox.query.filter_by(event_type=EVENT_RESERVATION_CONFIRMED).count(), 1
        )
        self.assertEqual(
            EmailOutbox.query.filter_by(event_type=EVENT_RESERVATION_CONFIRMED_INTERNAL).count(), 1
        )

    def test_invalid_payment_does_not_queue_confirmed_internal_email(self):
        reservation = self.reservation(self.tool())
        payment = self.rental_payment(reservation)
        event = self.checkout_event(payment, amount_total=1999)
        db.session.rollback()

        self.assertEqual(process_stripe_event(event), "requires_review")
        self.assertEqual(
            EmailOutbox.query.filter_by(event_type=EVENT_RESERVATION_CONFIRMED_INTERNAL).count(),
            0,
        )

    def test_failed_internal_confirmation_email_does_not_revert_the_paid_reservation(self):
        reservation = self.reservation(self.tool())
        payment = self.rental_payment(reservation)
        outbox_ids = []
        event = self.checkout_event(payment, event_id="evt_confirmation_internal_delivery_failure")
        db.session.rollback()
        self.assertEqual(process_stripe_event(event, outbox_ids=outbox_ids), "confirmed")
        internal_email = EmailOutbox.query.filter_by(
            event_type=EVENT_RESERVATION_CONFIRMED_INTERNAL
        ).one()

        with patch(
            "app.services.email.outbox.send_resend_email",
            side_effect=ResendDeliveryError("x"),
        ):
            self.assertFalse(deliver_outbox_email(internal_email.id))

        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_PAID)
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_CONFIRMED)
        self.assertEqual(db.session.get(EmailOutbox, internal_email.id).status, EMAIL_OUTBOX_STATUS_FAILED)

    def test_delivery_request_queues_customer_and_admin_emails_once(self):
        tool_id = self.tool(delivery_available=True).id
        db.session.rollback()
        outbox_ids = []
        reservation = create_reservation(
            tool_id,
            date(2026, 10, 1),
            date(2026, 10, 2),
            "Cliente <transporte>",
            "cliente@example.test",
            "600000000",
            True,
            True,
            "delivery",
            "Calle <entrega> 1",
            outbox_ids=outbox_ids,
        )

        self.assertEqual(reservation.status, "pending_review")
        self.assertEqual(len(outbox_ids), 2)
        emails = {email.event_type: email for email in EmailOutbox.query.all()}
        customer = emails["reservation_pending_review_customer"]
        admin = emails["reservation_pending_review_admin"]
        self.assertEqual(customer.recipient, "cliente@example.test")
        self.assertEqual(admin.recipient, "operations@example.test")
        self.assertIn("Todavía no debes realizar ningún pago", customer.text_body)
        self.assertIn("Calle &lt;entrega&gt; 1", customer.html_body)
        self.assertNotIn("Total final", customer.text_body)
        admin_url = f"https://api.example.test/admin/reservation/details/?id={reservation.id}"
        self.assertIn("Gestionar reserva", admin.html_body)
        self.assertIn(admin_url, admin.html_body)
        self.assertIn("Gestionar reserva", admin.text_body)
        self.assertIn(admin_url, admin.text_body)
        parsed_url = urlparse(admin_url)
        self.assertEqual(parsed_url.path, "/admin/reservation/details/")
        self.assertEqual(parse_qs(parsed_url.query), {"id": [str(reservation.id)]})
        self.assertNotIn("token", admin_url)
        self.assertNotIn("auth", admin_url)
        self.assertIn("Cliente &lt;transporte&gt;", admin.html_body)

        db.session.rollback()
        with db.session.begin():
            repeated = queue_delivery_review_requested(db.session, reservation)
        self.assertEqual(len([email for email in repeated if email is not None]), 2)
        self.assertEqual(EmailOutbox.query.count(), 2)

    def test_delivery_review_queues_payment_email_after_quote_is_frozen(self):
        tool_id = self.tool(delivery_available=True).id
        db.session.rollback()
        reservation = create_reservation(
            tool_id,
            date(2026, 10, 1),
            date(2026, 10, 2),
            "Cliente de transporte",
            "cliente@example.test",
            "600000000",
            True,
            True,
            "delivery",
            "Calle de prueba 1",
        )
        reservation_id = reservation.id
        self.assertEqual(
            EmailOutbox.query.filter_by(event_type="reservation_pending_payment").count(), 0
        )
        db.session.rollback()

        outbox_ids = []
        review_delivery_reservation(
            reservation_id,
            Decimal("12.50"),
            now=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
            outbox_ids=outbox_ids,
        )

        email = EmailOutbox.query.filter_by(event_type="reservation_pending_payment").one()
        self.assertEqual(outbox_ids, [email.id])
        self.assertIn("12.50 km", email.text_body)
        self.assertIn("1.50 €/km", email.text_body)
        self.assertIn("18.75 €", email.text_body)
        self.assertIn("38.75 €", email.text_body)
        self.assertIn(
            f"http://localhost:3000/mi-cuenta/reservas/{reservation_id}", email.html_body
        )
        self.assertNotIn("https://api.example.test", email.html_body)

    def test_failed_delivery_review_email_never_reverts_the_payment_transition(self):
        tool_id = self.tool(delivery_available=True).id
        db.session.rollback()
        reservation = create_reservation(
            tool_id,
            date(2026, 10, 1),
            date(2026, 10, 2),
            "Cliente de transporte",
            "cliente@example.test",
            "600000000",
            True,
            True,
            "delivery",
            "Calle de prueba 1",
        )
        reservation_id = reservation.id
        db.session.rollback()
        outbox_ids = []
        review_delivery_reservation(reservation_id, Decimal("12.50"), outbox_ids=outbox_ids)

        with patch("app.services.email.outbox.send_resend_email", side_effect=ResendDeliveryError("x")):
            self.assertFalse(deliver_outbox_email(outbox_ids[0]))

        self.assertEqual(db.session.get(Reservation, reservation_id).status, "pending_payment")
        self.assertEqual(db.session.get(EmailOutbox, outbox_ids[0]).status, EMAIL_OUTBOX_STATUS_FAILED)

    def test_failed_deposit_request_email_never_reverts_the_pending_checkout(self):
        reservation = self.reservation(
            self.tool(Decimal("100.00")), status=RESERVATION_STATUS_CONFIRMED
        )
        rental_payment = self.rental_payment(reservation)
        rental_payment.status = PAYMENT_STATUS_PAID
        db.session.commit()
        reservation_id = reservation.id
        checkout = type(
            "Checkout",
            (),
            {
                "id": "cs_deposit_email_failure",
                "url": "https://checkout.stripe.test/c/pay/cs_deposit_email_failure",
                "status": "open",
            },
        )()
        outbox_ids: list[int] = []
        db.session.rollback()

        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=checkout,
        ):
            start_or_recover_deposit_checkout(
                reservation_id,
                queue_request_email=True,
                outbox_ids=outbox_ids,
            )

        with patch(
            "app.services.email.outbox.send_resend_email",
            side_effect=ResendDeliveryError("x"),
        ):
            self.assertFalse(deliver_outbox_email(outbox_ids[0]))

        deposit = Payment.query.filter_by(
            reservation_id=reservation_id,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
        ).one()
        self.assertEqual(db.session.get(Reservation, reservation_id).status, RESERVATION_STATUS_CONFIRMED)
        self.assertEqual(deposit.status, PAYMENT_STATUS_PENDING_AUTHORIZATION)
        self.assertEqual(deposit.provider_checkout_id, "cs_deposit_email_failure")
        self.assertEqual(db.session.get(EmailOutbox, outbox_ids[0]).status, EMAIL_OUTBOX_STATUS_FAILED)

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
        reservation = db.session.get(Reservation, reservation_id)
        reservation.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        reservation.returned_at = datetime.now(timezone.utc)
        db.session.commit()
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
        second.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        second.returned_at = datetime.now(timezone.utc)
        db.session.commit()
        intent = {"status": "succeeded", "amount_received": 4000, "latest_charge": "ch_capture"}
        with patch("app.services.deposit_authorizations.stripe.PaymentIntent.capture", return_value=intent):
            capture_deposit_authorization(second_id, Decimal("40.00"), "Nota interna privada", outbox_ids=ids)
        captured = EmailOutbox.query.filter_by(event_type="deposit_captured").one()
        self.assertIn("40.00 €", captured.html_body)
        self.assertNotIn("Nota interna privada", captured.html_body)
        self.assertNotIn("Nota interna privada", captured.text_body)

    def test_authorized_deposit_queues_one_customer_and_one_internal_operational_email(self):
        reservation = self.reservation(self.tool(Decimal("100.00")), status=RESERVATION_STATUS_CONFIRMED)
        payment = self.deposit_payment(reservation)
        ids = []
        event = self.deposit_event(payment, event_id="evt_authorized_internal")
        db.session.rollback()

        self.assertEqual(process_stripe_deposit_event(event, outbox_ids=ids), "authorized")
        self.assertEqual(process_stripe_deposit_event(event, outbox_ids=ids), "duplicate")

        customer_email = EmailOutbox.query.filter_by(event_type=EVENT_DEPOSIT_AUTHORIZED).one()
        internal_email = EmailOutbox.query.filter_by(
            event_type=EVENT_DEPOSIT_AUTHORIZED_INTERNAL
        ).one()
        self.assertEqual(customer_email.recipient, "cliente@example.test")
        self.assertEqual(internal_email.recipient, "operations@example.test")
        self.assertIn(reservation.tool.name, internal_email.html_body)
        self.assertIn("Cliente &lt;prueba&gt;", internal_email.html_body)
        self.assertIn("100.00 €", internal_email.html_body)
        self.assertIn("Válida hasta", internal_email.html_body)
        self.assertIn("hora peninsular", internal_email.text_body)
        self.assertEqual(EmailOutbox.query.count(), 2)
        self.assertEqual(len(ids), 2)

    def test_failed_internal_authorized_deposit_email_does_not_revert_authorization(self):
        reservation = self.reservation(self.tool(Decimal("100.00")), status=RESERVATION_STATUS_CONFIRMED)
        payment = self.deposit_payment(reservation)
        ids = []
        event = self.deposit_event(payment, event_id="evt_authorized_internal_delivery_failure")
        db.session.rollback()
        self.assertEqual(
            process_stripe_deposit_event(
                event,
                outbox_ids=ids,
            ),
            "authorized",
        )
        internal_email = EmailOutbox.query.filter_by(
            event_type=EVENT_DEPOSIT_AUTHORIZED_INTERNAL
        ).one()

        with patch(
            "app.services.email.outbox.send_resend_email",
            side_effect=ResendDeliveryError("x"),
        ):
            self.assertFalse(deliver_outbox_email(internal_email.id))

        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_AUTHORIZED)
        self.assertEqual(db.session.get(EmailOutbox, internal_email.id).status, EMAIL_OUTBOX_STATUS_FAILED)

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

        review_reservation = self.reservation(
            self.tool(Decimal("100.00")), status=RESERVATION_STATUS_CONFIRMED
        )
        review_payment = self.deposit_payment(review_reservation)
        review = self.deposit_event(review_payment, event_id="evt_invalid_authorization")
        review["data"]["object"]["amount_capturable"] = 9999
        db.session.rollback()
        self.assertEqual(process_stripe_deposit_event(review), "requires_review")
        self.assertEqual(
            EmailOutbox.query.filter_by(event_type=EVENT_DEPOSIT_AUTHORIZED_INTERNAL).count(),
            0,
        )

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
