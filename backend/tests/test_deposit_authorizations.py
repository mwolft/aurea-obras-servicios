import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "deposit-authorizations-test-secret"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_unit_test"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_unit_test"

from app import create_app
from app.extensions import db
from app.models import Payment, PaymentEvent, Reservation, Tool
from app.services.deposit_authorizations import (
    DepositAuthorizationError,
    capture_deposit_authorization,
    process_stripe_deposit_event,
    release_deposit_authorization,
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
    PAYMENT_WINDOW,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_PENDING_PAYMENT,
)
from app.services.reservations import create_reservation


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
            start_or_recover_deposit_checkout(reservation.id)
        self.assertEqual(
            Payment.query.filter_by(purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION).count(), 0
        )

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

    def test_authorization_webhook_is_idempotent_and_never_confirms_reservation(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        payment = Payment(reservation_id=reservation.id, provider=PAYMENT_PROVIDER_STRIPE, purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION, status=PAYMENT_STATUS_PENDING_AUTHORIZATION, amount=Decimal("100.00"), currency="eur", idempotency_key="deposit-event", expires_at=datetime.now(timezone.utc) + PAYMENT_WINDOW)
        db.session.add(payment); db.session.commit()
        event = self.intent_event(payment)
        db.session.rollback()
        self.assertEqual(process_stripe_deposit_event(event), "authorized")
        self.assertEqual(process_stripe_deposit_event(event), "duplicate")
        stored = db.session.get(Payment, payment.id)
        self.assertEqual(stored.status, PAYMENT_STATUS_AUTHORIZED)
        self.assertEqual(stored.authorized_amount, Decimal("100.00"))
        self.assertIsNotNone(stored.capture_before)
        self.assertEqual(PaymentEvent.query.count(), 1)
        self.assertEqual(db.session.get(Reservation, reservation.id).status, RESERVATION_STATUS_CONFIRMED)

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
        with patch("app.services.deposit_authorizations.stripe.PaymentIntent.cancel") as cancel:
            released = release_deposit_authorization(reservation_id)
        cancel.assert_called_once_with(payment.external_payment_id)
        self.assertEqual(released.status, PAYMENT_STATUS_RELEASED)
        self.assertIsNotNone(released.released_at)

    def test_partial_and_full_capture_and_reason_validation(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        reservation_id = reservation.id
        payment = self.authorize_payment(reservation)
        partial = {"status": "succeeded", "amount_received": 4000, "latest_charge": "ch_captured"}
        with patch("app.services.deposit_authorizations.stripe.PaymentIntent.capture", return_value=partial):
            captured = capture_deposit_authorization(reservation_id, Decimal("40.00"), "Daño documentado")
        self.assertEqual(captured.status, PAYMENT_STATUS_CAPTURED_PARTIALLY)
        self.assertEqual(captured.captured_amount, Decimal("40.00"))
        self.assertEqual(captured.capture_reason, "Daño documentado")
        with self.assertRaises(DepositAuthorizationError):
            capture_deposit_authorization(reservation_id, Decimal("1.00"), "")
        second = self.create_confirmed_reservation(self.create_tool(), start_date=date(2026, 10, 3), end_date=date(2026, 10, 4))
        second_id = second.id
        self.authorize_payment(second)
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
        with self.assertRaises(DepositAuthorizationError):
            release_deposit_authorization(reservation_id)
        self.assertEqual(db.session.get(Payment, payment.id).status, PAYMENT_STATUS_AUTHORIZATION_EXPIRED)

    def test_rental_charge_remains_separate_from_deposit_authorization(self):
        reservation = self.create_confirmed_reservation(self.create_tool())
        self.authorize_payment(reservation)
        self.assertEqual(Payment.query.filter_by(purpose=PAYMENT_PURPOSE_RENTAL_CHARGE).count(), 1)
        self.assertEqual(Payment.query.filter_by(purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION).count(), 1)
