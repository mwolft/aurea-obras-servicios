import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import stripe

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "deposit-authorizations-test-secret"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_unit_test"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_unit_test"

from app import create_app
from app.extensions import db
from app.models import EmailOutbox, Payment, PaymentEvent, Reservation, Tool
from app.services.deposit_authorizations import (
    DEPOSIT_CHECKOUT_WINDOW,
    DepositAuthorizationError,
    capture_deposit_authorization,
    process_stripe_deposit_event,
    reconcile_expired_deposit_authorization_for_closure,
    release_deposit_authorization,
    resend_deposit_authorization_request,
    start_or_recover_deposit_checkout,
)
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CAPTURED_PARTIALLY,
    PAYMENT_STATUS_PENDING_AUTHORIZATION,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_AUTHORIZATION_FAILED,
    PAYMENT_STATUS_RELEASED,
    PAYMENT_STATUS_REQUIRES_REVIEW,
    PAYMENT_WINDOW,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_CANCELLED,
    RESERVATION_STATUS_PENDING_PAYMENT,
    RESERVATION_STATUS_RETURNED_PENDING_CLOSURE,
)
from app.services.reservations import create_reservation
from app.services.email.rental import EVENT_DEPOSIT_AUTHORIZATION_REQUESTED
from app.services.stripe_checkout import ReservationPaymentStateError


class DepositAuthorizationTestCase(unittest.TestCase):
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

    def create_tool(self, deposit=Decimal("100.00")):
        tool = Tool(name="Deposit tool", category="Tests", daily_price=Decimal("10.00"), deposit_amount=deposit, pickup_available=True, delivery_available=False, is_published=True, is_available=True)
        db.session.add(tool)
        db.session.commit()
        return tool

    def create_confirmed_reservation(self, tool, **overrides):
        values = {
            "tool_id": tool.id, "start_date": date(2026, 9, 20), "end_date": date(2026, 9, 21),
            "status": RESERVATION_STATUS_CONFIRMED, "customer_name": "Deposit customer", "customer_email": "deposit@example.com", "customer_phone": "600000000",
            "terms_accepted": True, "privacy_accepted": True, "fulfillment_method": "pickup",
            "payment_expires_at": datetime.now(timezone.utc) + PAYMENT_WINDOW,
            "charged_days": 2, "daily_price_snapshot": Decimal("10.00"), "rental_amount": Decimal("20.00"), "delivery_amount": Decimal("0.00"), "total_amount": Decimal("20.00"),
            "deposit_amount_snapshot": Decimal(tool.deposit_amount),
        }
        values.update(overrides)
        reservation = Reservation(**values)
        db.session.add(reservation)
        db.session.flush()
        db.session.add(Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
            status=PAYMENT_STATUS_PAID,
            amount=Decimal("20.00"),
            currency="eur",
            idempotency_key=f"rental-paid-{reservation.id}",
            expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW,
        ))
        db.session.commit()
        return reservation

    @staticmethod
    def checkout(checkout_id="cs_deposit_1"):
        checkout = MagicMock()
        checkout.id = checkout_id
        checkout.url = f"https://checkout.stripe.test/c/pay/{checkout_id}"
        checkout.status = "open"
        return checkout

    @staticmethod
    def intent_event(payment, event_type="payment_intent.amount_capturable_updated", event_id="evt_deposit_1", **overrides):
        intent = {
            "id": "pi_deposit_1", "status": "requires_capture", "amount_capturable": 10000,
            "amount_received": 0,
            "metadata": {"payment_id": str(payment.id), "purpose": PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION},
            "latest_charge": {"id": "ch_deposit_1", "payment_method_details": {"card": {"capture_before": 1_800_000_000}}},
        }
        intent.update(overrides)
        return {"id": event_id, "type": event_type, "data": {"object": intent}}

    def authorize_payment(self, reservation):
        payment = Payment(reservation_id=reservation.id, provider=PAYMENT_PROVIDER_STRIPE, purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION, status=PAYMENT_STATUS_PENDING_AUTHORIZATION, amount=reservation.deposit_amount_snapshot, currency="eur", idempotency_key=f"deposit-payment-{reservation.id}", expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW)
        db.session.add(payment); db.session.commit()
        event = self.intent_event(
            payment,
            event_id=f"evt_deposit_{payment.id}",
            id=f"pi_deposit_{payment.id}",
            latest_charge={"id": f"ch_deposit_{payment.id}", "payment_method_details": {"card": {"capture_before": 1_800_000_000}}},
        )
        db.session.rollback()
        self.assertEqual(process_stripe_deposit_event(event), "authorized")
        stored = db.session.get(Payment, payment.id)
        db.session.rollback()
        return stored

    @staticmethod
    def pending_deposit(reservation, *, idempotency_key="deposit-pending"):
        payment = Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_PENDING_AUTHORIZATION,
            amount=Decimal(reservation.deposit_amount_snapshot),
            currency="eur",
            idempotency_key=idempotency_key,
            expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    def test_new_reservation_snapshots_deposit_and_tool_changes_do_not_change_it(self):
        tool = self.create_tool(Decimal("100.00"))
        tool_id = tool.id
        db.session.rollback()
        reservation = create_reservation(tool_id, date(2026, 10, 1), date(2026, 10, 2), "Snapshot customer", "snapshot@example.com", "600000001", True, True, "pickup")
        self.assertEqual(reservation.deposit_amount_snapshot, Decimal("100.00"))
        tool.deposit_amount = Decimal("250.00"); db.session.commit()
        self.assertEqual(db.session.get(Reservation, reservation.id).deposit_amount_snapshot, Decimal("100.00"))

    def test_zero_deposit_creates_no_payment(self):
        reservation = self.create_confirmed_reservation(self.create_tool(Decimal("0.00")))
        with self.assertRaises(Exception):
            start_or_recover_deposit_checkout(reservation.id, queue_request_email=True)
        self.assertEqual(
            Payment.query.filter_by(purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION).count(), 0
        )
        self.assertEqual(EmailOutbox.query.count(), 0)

    def test_starts_manual_card_authorization_and_reuses_checkout(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        checkout = self.checkout()
        db.session.rollback()
        with patch("app.services.deposit_authorizations.stripe.checkout.Session.create", return_value=checkout) as create:
            first = start_or_recover_deposit_checkout(reservation_id)
        payment = Payment.query.filter_by(purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION).one()
        self.assertEqual(payment.purpose, PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION)
        self.assertEqual(payment.status, PAYMENT_STATUS_PENDING_AUTHORIZATION)
        self.assertEqual(create.call_args.kwargs["payment_intent_data"]["capture_method"], "manual")
        self.assertEqual(create.call_args.kwargs["payment_method_types"], ["card"])
        self.assertEqual(create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"], 10000)
        self.assertEqual(first, checkout.url)
        db.session.rollback()
        with patch("app.services.deposit_authorizations.stripe.checkout.Session.retrieve", return_value=checkout) as retrieve:
            second = start_or_recover_deposit_checkout(reservation_id)
        self.assertEqual(second, checkout.url)
        retrieve.assert_called_once_with("cs_deposit_1")
        self.assertEqual(
            Payment.query.filter_by(purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION).count(), 1
        )

    def test_deposit_checkout_has_its_own_24_hour_window(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        requested_at = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        checkout = self.checkout("cs_deposit_24_hours")
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=checkout,
        ) as create:
            start_or_recover_deposit_checkout(reservation_id, now=requested_at)

        payment = Payment.query.filter_by(
            reservation_id=reservation_id,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
        ).one()
        self.assertEqual(
            payment.expires_at.replace(tzinfo=timezone.utc),
            requested_at + DEPOSIT_CHECKOUT_WINDOW,
        )
        self.assertEqual(
            create.call_args.kwargs["expires_at"],
            int((requested_at + DEPOSIT_CHECKOUT_WINDOW).timestamp()),
        )

    def test_manual_resend_reuses_open_checkout_without_second_deposit(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        requested_at = datetime.now(timezone.utc) - timedelta(hours=5)
        checkout = self.checkout("cs_deposit_resend")
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=checkout,
        ):
            start_or_recover_deposit_checkout(
                reservation_id,
                now=requested_at,
                queue_request_email=True,
            )
        payment = Payment.query.filter_by(
            reservation_id=reservation_id,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
        ).one()
        initial_email = EmailOutbox.query.one()
        initial_email.status = "sent"
        initial_email.sent_at = requested_at
        db.session.commit()
        outbox_ids: list[int] = []
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.retrieve",
            return_value=checkout,
        ):
            resend_deposit_authorization_request(
                reservation_id,
                now=datetime.now(timezone.utc),
                outbox_ids=outbox_ids,
            )

        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation_id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            1,
        )
        reminder = EmailOutbox.query.filter_by(event_type="deposit_authorization_reminder").one()
        self.assertEqual(outbox_ids, [reminder.id])
        self.assertIn(checkout.url, reminder.text_body)

    def test_manual_resend_is_rate_limited_and_never_creates_a_deposit(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        checkout = self.checkout("cs_deposit_rate_limit")
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=checkout,
        ):
            start_or_recover_deposit_checkout(
                reservation_id,
                queue_request_email=True,
            )
        email = EmailOutbox.query.one()
        email.status = "sent"
        email.sent_at = datetime.now(timezone.utc)
        db.session.commit()
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.retrieve",
            return_value=checkout,
        ):
            with self.assertRaisesRegex(ReservationPaymentStateError, "4 horas"):
                resend_deposit_authorization_request(reservation_id)
        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation_id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            1,
        )

    def test_elapsed_checkout_is_expired_in_stripe_before_a_new_request_is_created(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        requested_at = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        first_checkout = self.checkout("cs_deposit_elapsed")
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=first_checkout,
        ):
            start_or_recover_deposit_checkout(reservation_id, now=requested_at)

        open_checkout = self.checkout("cs_deposit_elapsed")
        expired_checkout = self.checkout("cs_deposit_elapsed")
        expired_checkout.status = "expired"
        replacement_checkout = self.checkout("cs_deposit_fresh")
        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.retrieve",
            return_value=open_checkout,
        ), patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.expire",
            return_value=expired_checkout,
        ) as expire, patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=replacement_checkout,
        ):
            self.assertEqual(
                start_or_recover_deposit_checkout(
                    reservation_id,
                    now=requested_at + DEPOSIT_CHECKOUT_WINDOW,
                ),
                replacement_checkout.url,
            )

        expire.assert_called_once_with("cs_deposit_elapsed")
        payments = Payment.query.filter_by(
            reservation_id=reservation_id,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
        ).order_by(Payment.id).all()
        self.assertEqual(len(payments), 2)
        self.assertEqual(payments[0].status, PAYMENT_STATUS_AUTHORIZATION_EXPIRED)
        self.assertEqual(payments[1].status, PAYMENT_STATUS_PENDING_AUTHORIZATION)

    def test_requesting_deposit_queues_one_customer_email_with_the_live_checkout(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        checkout = self.checkout("cs_deposit_email")
        outbox_ids: list[int] = []
        db.session.rollback()

        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=checkout,
        ):
            checkout_url = start_or_recover_deposit_checkout(
                reservation_id,
                queue_request_email=True,
                outbox_ids=outbox_ids,
            )

        payment = Payment.query.filter_by(
            reservation_id=reservation_id,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
        ).one()
        email = EmailOutbox.query.one()
        self.assertEqual(checkout_url, checkout.url)
        self.assertEqual(payment.status, PAYMENT_STATUS_PENDING_AUTHORIZATION)
        self.assertEqual(outbox_ids, [email.id])
        self.assertEqual(email.event_type, EVENT_DEPOSIT_AUTHORIZATION_REQUESTED)
        self.assertEqual(email.recipient, "deposit@example.com")
        self.assertIn(checkout.url, email.html_body)
        self.assertIn(checkout.url, email.text_body)
        self.assertIn("Deposit tool", email.html_body)
        self.assertIn("20/09/2026", email.text_body)
        self.assertIn("21/09/2026", email.text_body)
        self.assertIn("100.00 €", email.text_body)
        self.assertIn("retención temporal", email.text_body.lower())
        self.assertNotIn(payment.idempotency_key, email.html_body)

        db.session.rollback()
        repeated_outbox_ids: list[int] = []
        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.retrieve",
            return_value=checkout,
        ) as retrieve:
            repeated_url = start_or_recover_deposit_checkout(
                reservation_id,
                queue_request_email=True,
                outbox_ids=repeated_outbox_ids,
            )

        self.assertEqual(repeated_url, checkout.url)
        retrieve.assert_called_once_with("cs_deposit_email")
        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation_id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            1,
        )
        self.assertEqual(EmailOutbox.query.count(), 1)
        self.assertEqual(repeated_outbox_ids, [email.id])

    def test_deposit_request_rejects_unconfirmed_or_unpaid_reservations(self):
        unconfirmed = self.create_confirmed_reservation(self.create_tool())
        unconfirmed.status = RESERVATION_STATUS_PENDING_PAYMENT
        db.session.commit()
        unconfirmed_id = unconfirmed.id
        db.session.rollback()
        with self.assertRaises(ReservationPaymentStateError):
            start_or_recover_deposit_checkout(unconfirmed_id, queue_request_email=True)

        unpaid = self.create_confirmed_reservation(self.create_tool())
        rental_payment = Payment.query.filter_by(
            reservation_id=unpaid.id,
            purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
        ).one()
        rental_payment.status = "pending"
        db.session.commit()
        unpaid_id = unpaid.id
        db.session.rollback()
        with self.assertRaises(ReservationPaymentStateError):
            start_or_recover_deposit_checkout(unpaid_id, queue_request_email=True)

        self.assertEqual(EmailOutbox.query.count(), 0)

    def test_expired_checkout_can_be_replaced_but_completed_one_waits_for_webhook(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        first_checkout = self.checkout("cs_deposit_expired")
        db.session.rollback()
        with patch("app.services.deposit_authorizations.stripe.checkout.Session.create", return_value=first_checkout):
            start_or_recover_deposit_checkout(reservation_id)
        expired_checkout = self.checkout("cs_deposit_expired")
        expired_checkout.status = "expired"
        replacement_checkout = self.checkout("cs_deposit_replacement")
        with patch("app.services.deposit_authorizations.stripe.checkout.Session.retrieve", return_value=expired_checkout), patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create", return_value=replacement_checkout
        ):
            self.assertEqual(start_or_recover_deposit_checkout(reservation_id), replacement_checkout.url)
        self.assertEqual(
            Payment.query.filter_by(purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION).count(), 2
        )
        pending = Payment.query.filter_by(
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_PENDING_AUTHORIZATION,
        ).one()
        completed_checkout = self.checkout(pending.provider_checkout_id)
        completed_checkout.status = "complete"
        with patch("app.services.deposit_authorizations.stripe.checkout.Session.retrieve", return_value=completed_checkout):
            with self.assertRaises(Exception):
                start_or_recover_deposit_checkout(reservation_id)

    def test_elapsed_authorization_is_reconciled_then_reauthorized_without_changing_rental(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        original_total = reservation.total_amount
        original_snapshot = reservation.deposit_amount_snapshot
        rental_payment = Payment.query.filter_by(
            reservation_id=reservation_id, purpose=PAYMENT_PURPOSE_RENTAL_CHARGE
        ).one()
        expired_authorization = Payment(
            reservation_id=reservation_id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_AUTHORIZED,
            amount=original_snapshot,
            currency="eur",
            idempotency_key="expired-deposit-authorization",
            external_payment_id="pi_expired_deposit",
            provider_charge_id="ch_expired_deposit",
            authorized_amount=original_snapshot,
            authorized_at=datetime.now(timezone.utc) - timedelta(days=2),
            capture_before=datetime.now(timezone.utc) - timedelta(minutes=1),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.session.add(expired_authorization)
        db.session.commit()
        expired_id = expired_authorization.id
        db.session.rollback()

        replacement_checkout = self.checkout("cs_deposit_reauthorized")
        with patch(
            "app.services.deposit_authorizations.stripe.PaymentIntent.retrieve",
            return_value={"id": "pi_expired_deposit", "status": "canceled"},
        ) as retrieve_intent, patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=replacement_checkout,
        ):
            checkout_url = start_or_recover_deposit_checkout(reservation_id)

        retrieve_intent.assert_called_once_with("pi_expired_deposit")
        old_payment = db.session.get(Payment, expired_id)
        new_payment = Payment.query.filter_by(
            reservation_id=reservation_id,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
        ).order_by(Payment.id.desc()).first()
        refreshed_reservation = db.session.get(Reservation, reservation_id)
        self.assertEqual(checkout_url, replacement_checkout.url)
        self.assertEqual(old_payment.status, PAYMENT_STATUS_AUTHORIZATION_EXPIRED)
        self.assertEqual(old_payment.external_payment_id, "pi_expired_deposit")
        self.assertEqual(old_payment.provider_charge_id, "ch_expired_deposit")
        self.assertNotEqual(new_payment.id, old_payment.id)
        self.assertEqual(new_payment.status, PAYMENT_STATUS_PENDING_AUTHORIZATION)
        self.assertEqual(new_payment.amount, original_snapshot)
        self.assertEqual(refreshed_reservation.status, RESERVATION_STATUS_CONFIRMED)
        self.assertEqual(refreshed_reservation.total_amount, original_total)
        self.assertEqual(refreshed_reservation.deposit_amount_snapshot, original_snapshot)
        self.assertEqual(db.session.get(Payment, rental_payment.id).status, PAYMENT_STATUS_PAID)
        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation_id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            2,
        )

    def test_only_terminal_deposit_attempts_can_be_reauthorized(self):
        cases = (
            (PAYMENT_STATUS_AUTHORIZED, datetime.now(timezone.utc) + timedelta(days=1)),
            (PAYMENT_STATUS_REQUIRES_REVIEW, None),
            (PAYMENT_STATUS_RELEASED, None),
            (PAYMENT_STATUS_CAPTURED_PARTIALLY, None),
            (PAYMENT_STATUS_CAPTURED, None),
        )
        for status, capture_before in cases:
            with self.subTest(status=status):
                reservation = self.create_confirmed_reservation(
                    self.create_tool(),
                    start_date=date(2026, 10, 10),
                    end_date=date(2026, 10, 11),
                )
                db.session.add(Payment(
                    reservation_id=reservation.id,
                    provider=PAYMENT_PROVIDER_STRIPE,
                    purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                    status=status,
                    amount=reservation.deposit_amount_snapshot,
                    currency="eur",
                    idempotency_key=f"blocked-reauthorization-{reservation.id}",
                    external_payment_id=("pi_active" if status == PAYMENT_STATUS_AUTHORIZED else None),
                    authorized_amount=(reservation.deposit_amount_snapshot if status == PAYMENT_STATUS_AUTHORIZED else None),
                    capture_before=capture_before,
                    expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW,
                ))
                db.session.commit()
                before_count = Payment.query.filter_by(
                    reservation_id=reservation.id,
                    purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                ).count()
                db.session.rollback()
                with self.assertRaises(Exception):
                    start_or_recover_deposit_checkout(reservation.id)
                self.assertEqual(
                    Payment.query.filter_by(
                        reservation_id=reservation.id,
                        purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                    ).count(),
                    before_count,
                )

    def test_elapsed_authorization_that_stripe_reports_completed_requires_review(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        payment = Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_AUTHORIZED,
            amount=reservation.deposit_amount_snapshot,
            currency="eur",
            idempotency_key="completed-stale-deposit",
            external_payment_id="pi_completed_stale_deposit",
            authorized_amount=reservation.deposit_amount_snapshot,
            capture_before=datetime.now(timezone.utc) - timedelta(minutes=1),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.session.add(payment)
        db.session.commit()
        payment_id = payment.id
        db.session.rollback()

        with patch(
            "app.services.deposit_authorizations.stripe.PaymentIntent.retrieve",
            return_value={"id": "pi_completed_stale_deposit", "status": "succeeded"},
        ):
            with self.assertRaises(Exception):
                start_or_recover_deposit_checkout(reservation_id)

        db.session.rollback()
        self.assertEqual(
            db.session.get(Payment, payment_id).status,
            PAYMENT_STATUS_REQUIRES_REVIEW,
        )
        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation.id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            1,
        )

    def test_returned_expired_authorization_is_reconciled_without_creating_a_replacement(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        original_total = reservation.total_amount
        original_snapshot = reservation.deposit_amount_snapshot
        rental_payment = Payment.query.filter_by(
            reservation_id=reservation_id,
            purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
        ).one()
        deposit = Payment(
            reservation_id=reservation_id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_AUTHORIZED,
            amount=original_snapshot,
            currency="eur",
            idempotency_key="returned-expired-deposit",
            external_payment_id="pi_returned_expired",
            provider_charge_id="ch_returned_expired",
            authorized_amount=original_snapshot,
            authorized_at=datetime.now(timezone.utc) - timedelta(days=2),
            capture_before=datetime.now(timezone.utc) - timedelta(minutes=1),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        reservation.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        reservation.returned_at = datetime.now(timezone.utc)
        db.session.add(deposit)
        db.session.commit()
        deposit_id = deposit.id
        db.session.rollback()

        with patch(
            "app.services.deposit_authorizations.stripe.PaymentIntent.retrieve",
            return_value={"id": "pi_returned_expired", "status": "canceled"},
        ) as retrieve:
            reconciled = reconcile_expired_deposit_authorization_for_closure(reservation_id)

        retrieve.assert_called_once_with("pi_returned_expired")
        self.assertEqual(reconciled.id, deposit_id)
        stored = db.session.get(Payment, deposit_id)
        self.assertEqual(stored.status, PAYMENT_STATUS_AUTHORIZATION_EXPIRED)
        self.assertEqual(stored.external_payment_id, "pi_returned_expired")
        self.assertEqual(stored.provider_charge_id, "ch_returned_expired")
        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation_id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            1,
        )
        refreshed = db.session.get(Reservation, reservation_id)
        self.assertEqual(refreshed.total_amount, original_total)
        self.assertEqual(refreshed.deposit_amount_snapshot, original_snapshot)
        self.assertEqual(db.session.get(Payment, rental_payment.id).status, PAYMENT_STATUS_PAID)

    def test_unexpected_stripe_status_blocks_returned_expired_deposit_closure_for_review(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        deposit = Payment(
            reservation_id=reservation_id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_AUTHORIZED,
            amount=reservation.deposit_amount_snapshot,
            currency="eur",
            idempotency_key="returned-ambiguous-deposit",
            external_payment_id="pi_returned_ambiguous",
            authorized_amount=reservation.deposit_amount_snapshot,
            capture_before=datetime.now(timezone.utc) - timedelta(minutes=1),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        reservation.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        reservation.returned_at = datetime.now(timezone.utc)
        db.session.add(deposit)
        db.session.commit()
        db.session.rollback()

        with patch(
            "app.services.deposit_authorizations.stripe.PaymentIntent.retrieve",
            return_value={"id": "pi_returned_ambiguous", "status": "requires_capture"},
        ):
            with self.assertRaisesRegex(DepositAuthorizationError, "requiere revisión"):
                reconcile_expired_deposit_authorization_for_closure(reservation_id)

        self.assertEqual(db.session.get(Payment, deposit.id).status, PAYMENT_STATUS_REQUIRES_REVIEW)

    def test_returned_reservation_cannot_start_a_replacement_deposit_authorization(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        reservation.returned_at = datetime.now(timezone.utc)
        db.session.commit()
        reservation_id = reservation.id
        db.session.rollback()

        with patch("app.services.deposit_authorizations.stripe.checkout.Session.create") as create:
            with self.assertRaises(ReservationPaymentStateError):
                start_or_recover_deposit_checkout(reservation_id)

        create.assert_not_called()
        self.assertEqual(
            Payment.query.filter_by(
                reservation_id=reservation_id,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).count(),
            0,
        )

    def test_authorization_webhook_is_idempotent_and_never_confirms_reservation(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        payment = Payment(reservation_id=reservation.id, provider=PAYMENT_PROVIDER_STRIPE, purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION, status=PAYMENT_STATUS_PENDING_AUTHORIZATION, amount=Decimal("100.00"), currency="eur", idempotency_key="deposit-event", expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW)
        db.session.add(payment); db.session.commit()
        event = self.intent_event(payment)
        db.session.rollback()
        with patch("app.services.deposit_authorizations.stripe.Charge.retrieve") as retrieve_charge:
            self.assertEqual(process_stripe_deposit_event(event), "authorized")
            self.assertEqual(process_stripe_deposit_event(event), "duplicate")
        retrieve_charge.assert_not_called()
        stored = db.session.get(Payment, payment.id)
        self.assertEqual(stored.status, PAYMENT_STATUS_AUTHORIZED)
        self.assertEqual(stored.authorized_amount, Decimal("100.00"))
        self.assertIsNotNone(stored.capture_before)
        self.assertEqual(PaymentEvent.query.count(), 1)
        self.assertEqual(EmailOutbox.query.filter_by(event_type="deposit_authorized").count(), 1)
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_CONFIRMED)

    def test_authorization_webhook_retrieves_string_latest_charge_before_authorizing(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        payment = self.pending_deposit(reservation, idempotency_key="deposit-string-charge")
        event = self.intent_event(
            payment,
            event_id="evt_string_charge",
            latest_charge="ch_string_charge",
        )
        charge = {
            "id": "ch_string_charge",
            "payment_intent": "pi_deposit_1",
            "payment_method_details": {"card": {"capture_before": 1_800_000_000}},
        }

        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.Charge.retrieve",
            return_value=charge,
        ) as retrieve_charge:
            self.assertEqual(process_stripe_deposit_event(event), "authorized")
            self.assertEqual(process_stripe_deposit_event(event), "duplicate")

        retrieve_charge.assert_called_once_with("ch_string_charge")
        stored = db.session.get(Payment, payment.id)
        self.assertEqual(stored.status, PAYMENT_STATUS_AUTHORIZED)
        self.assertEqual(stored.provider_charge_id, "ch_string_charge")
        self.assertEqual(stored.authorized_amount, Decimal("100.00"))
        self.assertIsNotNone(stored.capture_before)
        self.assertEqual(EmailOutbox.query.filter_by(event_type="deposit_authorized").count(), 1)

    def test_authorization_webhook_requires_review_when_string_charge_cannot_be_retrieved(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        payment = self.pending_deposit(reservation, idempotency_key="deposit-charge-retrieval-failure")
        event = self.intent_event(
            payment,
            event_id="evt_charge_retrieval_failure",
            latest_charge="ch_unavailable",
        )

        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.Charge.retrieve",
            side_effect=stripe.StripeError("unavailable"),
        ):
            self.assertEqual(process_stripe_deposit_event(event), "requires_review")

        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_REQUIRES_REVIEW)
        self.assertEqual(EmailOutbox.query.filter_by(event_type="deposit_authorized").count(), 0)

    def test_authorization_webhook_requires_review_when_retrieved_charge_has_no_capture_before(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        payment = self.pending_deposit(reservation, idempotency_key="deposit-charge-without-deadline")
        event = self.intent_event(
            payment,
            event_id="evt_charge_without_deadline",
            latest_charge="ch_without_deadline",
        )
        charge = {"id": "ch_without_deadline", "payment_intent": "pi_deposit_1"}

        db.session.rollback()
        with patch(
            "app.services.deposit_authorizations.stripe.Charge.retrieve",
            return_value=charge,
        ):
            self.assertEqual(process_stripe_deposit_event(event), "requires_review")

        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_REQUIRES_REVIEW)
        self.assertEqual(EmailOutbox.query.filter_by(event_type="deposit_authorized").count(), 0)

    def test_authorization_webhook_requires_review_before_charge_lookup_for_invalid_intent(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        payment = self.pending_deposit(reservation, idempotency_key="deposit-invalid-intent")
        invalid_status = self.intent_event(
            payment,
            event_id="evt_invalid_intent_status",
            status="processing",
            latest_charge="ch_should_not_load",
        )
        db.session.rollback()
        with patch("app.services.deposit_authorizations.stripe.Charge.retrieve") as retrieve_charge:
            self.assertEqual(process_stripe_deposit_event(invalid_status), "requires_review")
        retrieve_charge.assert_not_called()
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_REQUIRES_REVIEW)

        second = self.create_confirmed_reservation(
            self.create_tool(), start_date=date(2026, 9, 22), end_date=date(2026, 9, 23)
        )
        second_payment = self.pending_deposit(second, idempotency_key="deposit-invalid-amount")
        invalid_amount = self.intent_event(
            second_payment,
            event_id="evt_invalid_capturable_amount",
            id="pi_deposit_2",
            amount_capturable=9999,
            latest_charge="ch_should_not_load_either",
        )
        db.session.rollback()
        with patch("app.services.deposit_authorizations.stripe.Charge.retrieve") as retrieve_charge:
            self.assertEqual(process_stripe_deposit_event(invalid_amount), "requires_review")
        retrieve_charge.assert_not_called()
        self.assertEqual(db.session.get(Payment, second_payment.id).status, PAYMENT_STATUS_REQUIRES_REVIEW)

    def test_late_authorization_for_cancelled_reservation_is_cancelled_not_retained(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation.status = RESERVATION_STATUS_CANCELLED
        payment = Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_PENDING_AUTHORIZATION,
            amount=Decimal("100.00"),
            currency="eur",
            idempotency_key="cancelled-reservation-late-deposit",
            expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW,
        )
        db.session.add(payment)
        db.session.commit()
        event = self.intent_event(payment, event_id="evt_late_cancelled_deposit")
        db.session.rollback()

        with patch(
            "app.services.deposit_authorizations.stripe.PaymentIntent.cancel",
            return_value={"id": "pi_deposit_1", "status": "canceled"},
        ) as cancel_intent:
            self.assertEqual(process_stripe_deposit_event(event), PAYMENT_STATUS_RELEASED)

        cancel_intent.assert_called_once_with("pi_deposit_1")
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_CANCELLED)
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_RELEASED)
        self.assertEqual(PaymentEvent.query.count(), 1)

    def test_sca_intermediate_and_stripe_failure_or_cancellation_do_not_confirm_reservation(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        payment = Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_PENDING_AUTHORIZATION,
            amount=Decimal("100.00"),
            currency="eur",
            idempotency_key="deposit-sca",
            expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW,
        )
        db.session.add(payment)
        db.session.commit()
        sca_event = self.intent_event(payment, event_type="payment_intent.requires_action", event_id="evt_sca")
        self.assertEqual(process_stripe_deposit_event(sca_event), "ignored")
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_PENDING_AUTHORIZATION)
        failed_event = self.intent_event(payment, event_type="payment_intent.payment_failed", event_id="evt_failed")
        db.session.rollback()
        self.assertEqual(process_stripe_deposit_event(failed_event), "authorization_failed")
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_AUTHORIZATION_FAILED)
        cancelled_event = self.intent_event(payment, event_type="payment_intent.canceled", event_id="evt_cancelled")
        db.session.rollback()
        self.assertEqual(process_stripe_deposit_event(cancelled_event), PAYMENT_STATUS_AUTHORIZATION_EXPIRED)
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_CONFIRMED)

    def test_release_only_after_stripe_accepts_it(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        payment = self.authorize_payment(reservation)
        reservation.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        reservation.returned_at = datetime.now(timezone.utc)
        db.session.commit()
        with patch("app.services.deposit_authorizations.stripe.PaymentIntent.cancel") as cancel:
            released = release_deposit_authorization(reservation_id)
        cancel.assert_called_once_with(payment.external_payment_id)
        self.assertEqual(released.status, PAYMENT_STATUS_RELEASED)
        self.assertIsNotNone(released.released_at)

    def test_partial_and_full_capture_and_reason_validation(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        payment = self.authorize_payment(reservation)
        reservation.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        reservation.returned_at = datetime.now(timezone.utc)
        db.session.commit()
        partial = {"status": "succeeded", "amount_received": 4000, "latest_charge": "ch_captured"}
        with patch("app.services.deposit_authorizations.stripe.PaymentIntent.capture", return_value=partial):
            captured = capture_deposit_authorization(reservation_id, Decimal("40.00"), "Daño documentado")
        self.assertEqual(captured.status, PAYMENT_STATUS_CAPTURED_PARTIALLY)
        self.assertEqual(captured.captured_amount, Decimal("40.00"))
        self.assertEqual(captured.capture_reason, "Daño documentado")
        with self.assertRaises(DepositAuthorizationError):
            capture_deposit_authorization(reservation_id, Decimal("1.00"), "")
        db.session.rollback()
        with self.assertRaises(DepositAuthorizationError):
            capture_deposit_authorization(reservation_id, Decimal("1.00"), "Segundo intento")
        second = self.create_confirmed_reservation(self.create_tool(), start_date=date(2026, 10, 3), end_date=date(2026, 10, 4))
        second_id = second.id
        self.authorize_payment(second)
        second.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        second.returned_at = datetime.now(timezone.utc)
        db.session.commit()
        full = {"status": "succeeded", "amount_received": 10000, "latest_charge": "ch_full"}
        with patch("app.services.deposit_authorizations.stripe.PaymentIntent.capture", return_value=full):
            captured_full = capture_deposit_authorization(second_id, Decimal("100.00"), "Daño total")
        self.assertEqual(captured_full.status, PAYMENT_STATUS_CAPTURED)
        db.session.rollback()
        with self.assertRaises(DepositAuthorizationError):
            capture_deposit_authorization(second_id, Decimal("101.00"), "Exceso")

    def test_unpaid_reservation_and_expired_authorization_are_rejected(self):
        pending = self.create_confirmed_reservation(self.create_tool(), status=RESERVATION_STATUS_PENDING_PAYMENT)
        pending_id = pending.id
        db.session.rollback()
        with self.assertRaises(Exception):
            start_or_recover_deposit_checkout(pending_id)
        reservation = self.create_confirmed_reservation(self.create_tool(), start_date=date(2026, 11, 1), end_date=date(2026, 11, 2))
        reservation_id = reservation.id
        payment = self.authorize_payment(reservation)
        payment.capture_before = datetime.now(timezone.utc) - timedelta(seconds=1); db.session.commit()
        reservation.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        reservation.returned_at = datetime.now(timezone.utc)
        db.session.commit()
        with self.assertRaises(DepositAuthorizationError):
            release_deposit_authorization(reservation_id)
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_AUTHORIZATION_EXPIRED)

    def test_deposit_resolution_is_rejected_until_the_reservation_is_returned(self):
        blocked_statuses = (
            RESERVATION_STATUS_CONFIRMED,
            "in_progress",
            "pending_review",
            RESERVATION_STATUS_PENDING_PAYMENT,
            "completed",
            "cancelled",
        )
        for status in blocked_statuses:
            with self.subTest(status=status):
                reservation = self.create_confirmed_reservation(
                    self.create_tool(),
                    start_date=date(2026, 10, 10),
                    end_date=date(2026, 10, 11),
                )
                reservation_id = reservation.id
                self.authorize_payment(reservation)
                reservation.status = status
                db.session.commit()

                with patch("app.services.deposit_authorizations.stripe.PaymentIntent.cancel") as cancel:
                    with self.assertRaisesRegex(
                        DepositAuthorizationError,
                        "después de registrar la devolución",
                    ):
                        release_deposit_authorization(reservation_id)
                cancel.assert_not_called()

                with patch("app.services.deposit_authorizations.stripe.PaymentIntent.capture") as capture:
                    with self.assertRaisesRegex(
                        DepositAuthorizationError,
                        "después de registrar la devolución",
                    ):
                        capture_deposit_authorization(
                            reservation_id, Decimal("10.00"), "Prueba de estado"
                        )
                capture.assert_not_called()

    def test_rental_charge_remains_separate_from_deposit_authorization(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        self.authorize_payment(reservation)
        self.assertEqual(Payment.query.filter_by(purpose=PAYMENT_PURPOSE_RENTAL_CHARGE).count(), 1)
        self.assertEqual(Payment.query.filter_by(purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION).count(), 1)
