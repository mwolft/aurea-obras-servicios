import os
import re
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "reservation-admin-test-secret"
os.environ["APP_ENV"] = "development"

from app import create_app
from app.admin import ReservationAdmin
from app.extensions import db
from app.models import EmailOutbox, Payment, Reservation, Tool, User
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING_AUTHORIZATION,
    PAYMENT_STATUS_RELEASED,
    PAYMENT_STATUS_REQUIRES_REVIEW,
)
from app.services.availability import is_tool_available
from app.services.reservations import (
    ReservationCancellationError,
    cancel_reservation,
    review_delivery_reservation,
)
from app.services.stripe_checkout import StripeConfigurationError


class ReservationAdminTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["STRIPE_SECRET_KEY"] = "sk_test_reservation_admin"
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()
        admin = User(name="Reservation admin", email="reservation-admin@example.com", is_admin=True)
        db.session.add(admin)
        db.session.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = admin.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def post_admin(self, path, data=None, csrf_path=None):
        form_page = self.client.get(csrf_path or path)
        token = re.search(
            r'name="csrf_token"[^>]*value="([^"]+)"', form_page.get_data(as_text=True)
        )
        self.assertIsNotNone(token)
        return self.client.post(path, data={**(data or {}), "csrf_token": token.group(1)})

    def create_pending_delivery_review(self, **overrides):
        tool = Tool(
            name="Delivery review tool",
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=Decimal("25.00"),
            pickup_available=True,
            delivery_available=True,
            delivery_price_per_km=Decimal("1.50"),
            is_published=True,
            is_available=True,
        )
        db.session.add(tool)
        db.session.flush()
        values = {
            "tool_id": tool.id,
            "start_date": date(2026, 8, 20),
            "end_date": date(2026, 8, 22),
            "status": "pending_review",
            "customer_name": "Customer Test",
            "customer_email": "customer@example.com",
            "customer_phone": "600000000",
            "terms_accepted": True,
            "privacy_accepted": True,
            "fulfillment_method": "delivery",
            "delivery_address": "Calle de prueba 1, Madrid",
        }
        values.update(overrides)
        reservation = Reservation(**values)
        db.session.add(reservation)
        db.session.commit()
        return reservation.id

    def create_cancellable_reservation(self, status: str, **overrides):
        tool = Tool(
            name="Cancellable reservation tool",
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=Decimal("25.00"),
            pickup_available=True,
            delivery_available=False,
            is_published=True,
            is_available=True,
        )
        db.session.add(tool)
        db.session.flush()
        values = {
            "tool_id": tool.id,
            "start_date": date(2026, 8, 20),
            "end_date": date(2026, 8, 22),
            "status": status,
            "customer_name": "Customer Test",
            "customer_email": "customer@example.com",
            "customer_phone": "600000000",
            "terms_accepted": True,
            "privacy_accepted": True,
            "fulfillment_method": "pickup",
        }
        if status == "pending_payment":
            values["payment_expires_at"] = datetime.now(timezone.utc) + timedelta(minutes=30)
        values.update(overrides)
        reservation = Reservation(**values)
        db.session.add(reservation)
        db.session.commit()
        return reservation.id

    def add_authorized_deposit(self, reservation_id: int, *, capture_before=None):
        reservation = db.session.get(Reservation, reservation_id)
        payment = Payment(
            reservation_id=reservation_id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_AUTHORIZED,
            amount=Decimal(reservation.deposit_amount_snapshot),
            currency="eur",
            idempotency_key=f"authorized-admin-deposit-{reservation_id}",
            external_payment_id=f"pi_authorized_admin_{reservation_id}",
            authorized_amount=Decimal(reservation.deposit_amount_snapshot),
            capture_before=capture_before or datetime.now(timezone.utc) + timedelta(days=1),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    def add_rental_charge(self, reservation_id: int):
        payment = Payment(
            reservation_id=reservation_id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
            status=PAYMENT_STATUS_PAID,
            amount=Decimal("20.00"),
            currency="eur",
            idempotency_key=f"paid-rental-{reservation_id}",
            external_payment_id=f"cs_paid_rental_{reservation_id}",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    def add_pending_deposit(self, reservation_id: int):
        reservation = db.session.get(Reservation, reservation_id)
        payment = Payment(
            reservation_id=reservation_id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=PAYMENT_STATUS_PENDING_AUTHORIZATION,
            amount=Decimal(reservation.deposit_amount_snapshot),
            currency="eur",
            idempotency_key=f"pending-admin-deposit-{reservation_id}",
            provider_checkout_id=f"cs_pending_admin_{reservation_id}",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    def test_admin_is_read_only_for_reservations(self):
        self.assertFalse(ReservationAdmin.can_create)
        self.assertFalse(ReservationAdmin.can_delete)
        self.assertFalse(ReservationAdmin.can_edit)

        response = self.client.get("/admin/reservation/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Crear", response.data)
        self.assertNotIn(b"Editar", response.data)
        self.assertNotIn(b"Confirmar pago", response.data)
        self.assertIn(b"Cliente", response.data)
        self.assertIn(b"Fecha inicio", response.data)
        self.assertIn(b"Fecha devoluci", response.data)

    def test_admin_shows_localized_status_including_expired_payment(self):
        pending_review_id = self.create_pending_delivery_review()
        expired_payment_id = self.create_cancellable_reservation(
            "pending_payment",
            payment_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        pending_review = db.session.get(Reservation, pending_review_id)
        expired_payment = db.session.get(Reservation, expired_payment_id)

        self.assertEqual(ReservationAdmin._status_label(pending_review), "Pendiente de revisión")
        self.assertEqual(ReservationAdmin._status_label(expired_payment), "Pago caducado")
        self.assertEqual(expired_payment.status, "pending_payment")

    def test_delivery_review_uses_domain_service_and_freezes_quote(self):
        reservation_id = self.create_pending_delivery_review()
        db.session.remove()

        list_response = self.client.get("/admin/reservation/")
        self.assertEqual(list_response.status_code, 200)
        self.assertIn(b"Revisar transporte", list_response.data)
        self.assertIn(
            f"/admin/reservation/review-delivery/{reservation_id}".encode(),
            list_response.data,
        )
        db.session.remove()

        with patch(
            "app.admin.review_delivery_reservation",
            wraps=review_delivery_reservation,
        ) as review_service:
            response = self.post_admin(
                f"/admin/reservation/review-delivery/{reservation_id}",
                data={
                    "billable_km": "12.50",
                    "total_amount": "0.01",
                    "rental_amount": "0.01",
                },
            )

        self.assertEqual(response.status_code, 302)
        review_service.assert_called_once()
        self.assertEqual(review_service.call_args.args, (reservation_id, Decimal("12.50")))
        self.assertIn("outbox_ids", review_service.call_args.kwargs)
        reservation = db.session.get(Reservation, reservation_id)
        self.assertEqual(reservation.status, "pending_payment")
        self.assertEqual(reservation.billable_km, Decimal("12.50"))
        self.assertEqual(reservation.charged_days, 3)
        self.assertEqual(reservation.rental_amount, Decimal("30.00"))
        self.assertEqual(reservation.delivery_amount, Decimal("18.75"))
        self.assertEqual(reservation.total_amount, Decimal("48.75"))
        payment_expires_at = reservation.payment_expires_at
        if payment_expires_at.tzinfo is None:
            payment_expires_at = payment_expires_at.replace(tzinfo=timezone.utc)
        self.assertAlmostEqual(
            (payment_expires_at - datetime.now(timezone.utc)).total_seconds(),
            timedelta(minutes=30).total_seconds(),
            delta=5,
        )

    def test_invalid_kilometres_do_not_change_reservation(self):
        reservation_id = self.create_pending_delivery_review()

        response = self.post_admin(
            f"/admin/reservation/review-delivery/{reservation_id}",
            data={"billable_km": "-1"},
        )

        self.assertEqual(response.status_code, 302)
        reservation = db.session.get(Reservation, reservation_id)
        self.assertEqual(reservation.status, "pending_review")
        self.assertIsNone(reservation.billable_km)
        self.assertIsNone(reservation.total_amount)

    def test_sensitive_admin_actions_require_a_csrf_token(self):
        reservation_id = self.create_pending_delivery_review()

        response = self.client.post(
            f"/admin/reservation/review-delivery/{reservation_id}", data={"billable_km": "12.50"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "pending_review")

    def test_stale_review_is_rejected_without_changes(self):
        reservation_id = self.create_pending_delivery_review(status="confirmed")
        csrf_reservation_id = self.create_pending_delivery_review()
        db.session.remove()

        response = self.post_admin(
            f"/admin/reservation/review-delivery/{reservation_id}",
            data={"billable_km": "12.50"},
            csrf_path=f"/admin/reservation/review-delivery/{csrf_reservation_id}",
        )

        self.assertEqual(response.status_code, 302)
        reservation = db.session.get(Reservation, reservation_id)
        self.assertEqual(reservation.status, "confirmed")
        self.assertIsNone(reservation.billable_km)
        self.assertIsNone(reservation.total_amount)

    def test_cancel_pending_review_uses_domain_service_and_releases_availability(self):
        reservation_id = self.create_pending_delivery_review()
        db.session.remove()

        with patch(
            "app.admin.cancel_reservation",
            wraps=cancel_reservation,
        ) as cancellation_service:
            response = self.post_admin(f"/admin/reservation/cancel/{reservation_id}")

        self.assertEqual(response.status_code, 302)
        cancellation_service.assert_called_once()
        self.assertEqual(cancellation_service.call_args.args, (reservation_id,))
        self.assertIn("outbox_ids", cancellation_service.call_args.kwargs)
        reservation = db.session.get(Reservation, reservation_id)
        self.assertEqual(reservation.status, "cancelled")
        self.assertTrue(
            is_tool_available(
                reservation.tool,
                reservation.start_date,
                reservation.end_date,
            )
        )

    def test_cancel_pending_payment_and_confirmed_reservations(self):
        pending_payment_id = self.create_cancellable_reservation("pending_payment")
        confirmed_id = self.create_cancellable_reservation("confirmed")
        db.session.remove()

        pending_response = self.post_admin(f"/admin/reservation/cancel/{pending_payment_id}")
        confirmed_response = self.post_admin(f"/admin/reservation/cancel/{confirmed_id}")

        self.assertEqual(pending_response.status_code, 302)
        self.assertEqual(confirmed_response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, pending_payment_id).status, "cancelled")
        self.assertEqual(db.session.get(Reservation, confirmed_id).status, "cancelled")

    def test_cancel_paid_reservation_keeps_rental_charge_and_shows_no_refund_warning(self):
        reservation_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("0.00")
        )
        rental_payment = self.add_rental_charge(reservation_id)
        rental_payment_id = rental_payment.id
        db.session.remove()

        page = self.client.get(f"/admin/reservation/cancel/{reservation_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"El alquiler ya est", page.data)
        self.assertIn(b"no realiza ning", page.data)

        response = self.post_admin(f"/admin/reservation/cancel/{reservation_id}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "cancelled")
        self.assertEqual(db.session.get(Payment, rental_payment_id).status, PAYMENT_STATUS_PAID)

    def test_cancel_pending_deposit_expires_checkout_before_cancelling(self):
        reservation_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        payment = self.add_pending_deposit(reservation_id)
        payment_id = payment.id
        checkout_id = payment.provider_checkout_id
        db.session.remove()

        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.retrieve",
            return_value={"id": checkout_id, "status": "open"},
        ), patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.expire",
            return_value={"id": checkout_id, "status": "expired"},
        ) as expire_checkout:
            page = self.client.get(f"/admin/reservation/cancel/{reservation_id}")
            self.assertIn(b"se invalidar", page.data)
            response = self.post_admin(f"/admin/reservation/cancel/{reservation_id}")

        self.assertEqual(response.status_code, 302)
        expire_checkout.assert_called_once_with(checkout_id)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "cancelled")
        self.assertEqual(
            db.session.get(Payment, payment_id).status,
            PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
        )

    def test_cancel_authorized_deposit_releases_hold_before_cancelling(self):
        reservation_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        payment = self.add_authorized_deposit(reservation_id)
        payment_id = payment.id
        payment_intent_id = payment.external_payment_id
        db.session.remove()

        with patch(
            "app.services.deposit_authorizations.stripe.PaymentIntent.cancel",
            return_value={"id": payment_intent_id, "status": "canceled"},
        ) as cancel_intent:
            page = self.client.get(f"/admin/reservation/cancel/{reservation_id}")
            self.assertIn(b"se liberar", page.data)
            response = self.post_admin(f"/admin/reservation/cancel/{reservation_id}")

        self.assertEqual(response.status_code, 302)
        cancel_intent.assert_called_once_with(payment_intent_id)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "cancelled")
        self.assertEqual(db.session.get(Payment, payment_id).status, PAYMENT_STATUS_RELEASED)

    def test_ambiguous_deposit_blocks_cancellation_and_is_marked_for_review(self):
        reservation_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        payment = self.add_authorized_deposit(reservation_id)
        payment_id = payment.id
        payment_intent_id = payment.external_payment_id
        db.session.remove()

        with patch(
            "app.services.deposit_authorizations.stripe.PaymentIntent.cancel",
            return_value={"id": payment_intent_id, "status": "requires_capture"},
        ):
            response = self.post_admin(f"/admin/reservation/cancel/{reservation_id}")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "confirmed")
        self.assertEqual(
            db.session.get(Payment, payment_id).status,
            PAYMENT_STATUS_REQUIRES_REVIEW,
        )

    def test_stripe_failure_blocks_cancellation_without_marking_the_reservation_cancelled(self):
        reservation_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        payment = self.add_authorized_deposit(reservation_id)
        payment_id = payment.id
        db.session.remove()

        with patch(
            "app.services.deposit_authorizations.stripe.PaymentIntent.cancel",
            side_effect=StripeConfigurationError("Stripe no configurado"),
        ):
            response = self.post_admin(f"/admin/reservation/cancel/{reservation_id}")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "confirmed")
        self.assertEqual(
            db.session.get(Payment, payment_id).status,
            PAYMENT_STATUS_REQUIRES_REVIEW,
        )

    def test_expired_deposit_can_be_cancelled_but_review_deposit_cannot(self):
        expired_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        review_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        db.session.add_all([
            Payment(
                reservation_id=expired_id,
                provider=PAYMENT_PROVIDER_STRIPE,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                status=PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
                amount=Decimal("75.00"),
                currency="eur",
                idempotency_key="cancel-expired-deposit",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ),
            Payment(
                reservation_id=review_id,
                provider=PAYMENT_PROVIDER_STRIPE,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                status=PAYMENT_STATUS_REQUIRES_REVIEW,
                amount=Decimal("75.00"),
                currency="eur",
                idempotency_key="cancel-review-deposit",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ),
        ])
        db.session.commit()
        db.session.remove()

        expired_response = self.post_admin(f"/admin/reservation/cancel/{expired_id}")
        review_page = self.client.get(f"/admin/reservation/cancel/{review_id}")

        self.assertEqual(expired_response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, expired_id).status, "cancelled")
        self.assertEqual(review_page.status_code, 302)
        self.assertEqual(db.session.get(Reservation, review_id).status, "confirmed")

    def test_repeated_cancellation_creates_one_cancellation_email(self):
        reservation_id = self.create_cancellable_reservation("confirmed")
        outbox_ids: list[int] = []
        db.session.remove()
        cancel_reservation(reservation_id, outbox_ids=outbox_ids)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "cancelled")
        db.session.remove()

        with self.assertRaises(ReservationCancellationError):
            cancel_reservation(reservation_id, outbox_ids=[])

        self.assertEqual(
            EmailOutbox.query.filter_by(
                event_type="reservation_cancelled", reservation_id=reservation_id
            ).count(),
            1,
        )

    def test_admin_can_complete_the_operational_flow_for_a_zero_deposit_reservation(self):
        reservation_id = self.create_cancellable_reservation(
            "confirmed",
            deposit_amount_snapshot=Decimal("0.00"),
        )
        db.session.remove()

        response = self.client.get("/admin/reservation/")
        self.assertIn(f"/admin/reservation/mark-delivered/{reservation_id}".encode(), response.data)

        response = self.post_admin(
            f"/admin/reservation/mark-delivered/{reservation_id}",
            data={"delivery_notes": "Entrega de prueba"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "in_progress")

        response = self.post_admin(
            f"/admin/reservation/mark-returned/{reservation_id}",
            data={"return_notes": "Devuelta correctamente", "return_incident_notes": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            db.session.get(Reservation, reservation_id).status,
            "returned_pending_closure",
        )

        response = self.post_admin(f"/admin/reservation/complete-rental/{reservation_id}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "completed")

    def test_admin_shows_reauthorize_only_for_an_expired_deposit(self):
        expired_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        active_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        db.session.add_all([
            Payment(
                reservation_id=expired_id,
                provider=PAYMENT_PROVIDER_STRIPE,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                status=PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
                amount=Decimal("75.00"),
                currency="eur",
                idempotency_key="expired-admin-deposit",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ),
            Payment(
                reservation_id=active_id,
                provider=PAYMENT_PROVIDER_STRIPE,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                status=PAYMENT_STATUS_AUTHORIZED,
                amount=Decimal("75.00"),
                currency="eur",
                idempotency_key="active-admin-deposit",
                external_payment_id="pi_active_admin",
                capture_before=datetime.now(timezone.utc) + timedelta(days=1),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            ),
        ])
        db.session.commit()

        response = self.client.get("/admin/reservation/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f"/admin/reservation/authorize-deposit/{expired_id}".encode(), response.data
        )
        self.assertIn(b"Reautorizar fianza", response.data)
        self.assertNotIn(
            f"/admin/reservation/authorize-deposit/{active_id}".encode(), response.data
        )

    def test_admin_requests_deposit_by_email_and_keeps_it_pending_until_stripe_confirms(self):
        reservation_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        self.add_rental_charge(reservation_id)
        checkout = type(
            "Checkout",
            (),
            {
                "id": "cs_admin_deposit_request",
                "url": "https://checkout.stripe.test/c/pay/cs_admin_deposit_request",
                "status": "open",
            },
        )()

        confirmation = self.client.get(f"/admin/reservation/authorize-deposit/{reservation_id}")
        self.assertEqual(confirmation.status_code, 200)
        self.assertIn(b"Solicitar fianza", confirmation.data)
        self.assertIn(b"correo", confirmation.data)

        with patch(
            "app.services.deposit_authorizations.stripe.checkout.Session.create",
            return_value=checkout,
        ), patch("app.services.email.outbox.send_resend_email", return_value="re_deposit_request"):
            response = self.post_admin(f"/admin/reservation/authorize-deposit/{reservation_id}")

        self.assertEqual(response.status_code, 302)
        payment = Payment.query.filter_by(
            reservation_id=reservation_id,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
        ).one()
        email = EmailOutbox.query.one()
        self.assertEqual(payment.status, PAYMENT_STATUS_PENDING_AUTHORIZATION)
        self.assertEqual(email.status, "sent")
        self.assertIn(checkout.url, email.html_body)

        listing = self.client.get("/admin/reservation/")
        self.assertIn(b"Solicitud enviada", listing.data)
        self.assertIn(b"Esperando autorizaci", listing.data)
        self.assertNotIn(
            f"/admin/reservation/authorize-deposit/{reservation_id}".encode(), listing.data
        )

    def test_admin_offers_new_request_after_checkout_expiry_and_controlled_resend_when_open(self):
        expired_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        waiting_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        self.add_rental_charge(expired_id)
        self.add_rental_charge(waiting_id)
        expired = self.add_pending_deposit(expired_id)
        expired.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        waiting = self.add_pending_deposit(waiting_id)
        waiting.expires_at = datetime.now(timezone.utc) + timedelta(hours=12)
        db.session.add_all([
            EmailOutbox(
                event_type="deposit_authorization_requested",
                reservation_id=expired_id,
                recipient="customer@example.com",
                subject="Solicitud",
                text_body="Texto",
                html_body="<p>Texto</p>",
                idempotency_key=f"deposit:{expired.id}:authorization_requested",
                status="sent",
                sent_at=datetime.now(timezone.utc) - timedelta(hours=25),
            ),
            EmailOutbox(
                event_type="deposit_authorization_requested",
                reservation_id=waiting_id,
                recipient="customer@example.com",
                subject="Solicitud",
                text_body="Texto",
                html_body="<p>Texto</p>",
                idempotency_key=f"deposit:{waiting.id}:authorization_requested",
                status="sent",
                sent_at=datetime.now(timezone.utc) - timedelta(hours=5),
            ),
        ])
        db.session.commit()

        response = self.client.get("/admin/reservation/")

        self.assertIn(b"Generar nueva solicitud", response.data)
        self.assertIn(
            f"/admin/reservation/authorize-deposit/{expired_id}".encode(), response.data
        )
        self.assertIn(b"Reenviar solicitud", response.data)
        self.assertIn(
            f"/admin/reservation/resend-deposit-request/{waiting_id}".encode(), response.data
        )

    def test_admin_only_shows_deposit_resolution_actions_after_return(self):
        confirmed_id = self.create_cancellable_reservation(
            "confirmed", deposit_amount_snapshot=Decimal("75.00")
        )
        in_progress_id = self.create_cancellable_reservation(
            "in_progress", deposit_amount_snapshot=Decimal("75.00")
        )
        returned_id = self.create_cancellable_reservation(
            "returned_pending_closure",
            deposit_amount_snapshot=Decimal("75.00"),
            returned_at=datetime.now(timezone.utc),
        )
        expired_returned_id = self.create_cancellable_reservation(
            "returned_pending_closure",
            deposit_amount_snapshot=Decimal("75.00"),
            returned_at=datetime.now(timezone.utc),
        )
        self.add_authorized_deposit(confirmed_id)
        self.add_authorized_deposit(in_progress_id)
        self.add_authorized_deposit(returned_id)
        self.add_authorized_deposit(
            expired_returned_id,
            capture_before=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        response = self.client.get("/admin/reservation/")

        self.assertEqual(response.status_code, 200)
        for reservation_id in (confirmed_id, in_progress_id, expired_returned_id):
            self.assertNotIn(
                f"/admin/reservation/release-deposit/{reservation_id}".encode(), response.data
            )
            self.assertNotIn(
                f"/admin/reservation/capture-deposit/{reservation_id}".encode(), response.data
            )
        self.assertIn(
            f"/admin/reservation/release-deposit/{returned_id}".encode(), response.data
        )
        self.assertIn(
            f"/admin/reservation/capture-deposit/{returned_id}".encode(), response.data
        )
        self.assertIn(
            f"/admin/reservation/mark-delivered/{confirmed_id}".encode(), response.data
        )
        self.assertIn(
            f"/admin/reservation/mark-returned/{in_progress_id}".encode(), response.data
        )
        self.assertIn(
            f"/admin/reservation/complete-rental-without-charge/{expired_returned_id}".encode(),
            response.data,
        )
        self.assertNotIn(
            f"/admin/reservation/authorize-deposit/{expired_returned_id}".encode(),
            response.data,
        )

    def test_admin_can_release_a_valid_deposit_after_return_and_close_the_rental(self):
        reservation_id = self.create_cancellable_reservation(
            "returned_pending_closure",
            deposit_amount_snapshot=Decimal("75.00"),
            returned_at=datetime.now(timezone.utc),
        )
        self.add_authorized_deposit(reservation_id)
        db.session.remove()

        with patch("app.services.deposit_authorizations.stripe.PaymentIntent.cancel"):
            response = self.post_admin(f"/admin/reservation/release-deposit/{reservation_id}")

        self.assertEqual(response.status_code, 302)
        payment = Payment.query.filter_by(reservation_id=reservation_id).one()
        self.assertEqual(payment.status, "released")

        response = self.client.get("/admin/reservation/")
        self.assertIn(f"/admin/reservation/complete-rental/{reservation_id}".encode(), response.data)

        response = self.post_admin(f"/admin/reservation/complete-rental/{reservation_id}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "completed")

    def test_admin_closes_an_expired_returned_deposit_only_after_confirmation(self):
        reservation_id = self.create_cancellable_reservation(
            "returned_pending_closure",
            deposit_amount_snapshot=Decimal("75.00"),
            returned_at=datetime.now(timezone.utc),
        )
        payment = self.add_authorized_deposit(
            reservation_id,
            capture_before=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        payment_id = payment.id
        payment_intent_id = payment.external_payment_id
        db.session.remove()
        path = f"/admin/reservation/complete-rental-without-charge/{reservation_id}"

        confirmation = self.client.get(path)
        self.assertEqual(confirmation.status_code, 200)
        self.assertIn(b"Confirmar cierre sin cargo", confirmation.data)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "returned_pending_closure")

        with patch(
            "app.services.deposit_authorizations.stripe.PaymentIntent.retrieve",
            return_value={"id": payment_intent_id, "status": "canceled"},
        ):
            response = self.post_admin(path)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, reservation_id).status, "completed")
        self.assertEqual(db.session.get(Payment, payment_id).status, PAYMENT_STATUS_AUTHORIZATION_EXPIRED)
        self.assertEqual(Payment.query.filter_by(reservation_id=reservation_id).count(), 1)

    def test_admin_hides_close_without_charge_when_a_return_incident_exists(self):
        reservation_id = self.create_cancellable_reservation(
            "returned_pending_closure",
            deposit_amount_snapshot=Decimal("75.00"),
            returned_at=datetime.now(timezone.utc),
            return_incident_notes="Incidencia pendiente",
        )
        payment = self.add_authorized_deposit(reservation_id)
        payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
        db.session.commit()

        response = self.client.get("/admin/reservation/")
        self.assertNotIn(
            f"/admin/reservation/complete-rental-without-charge/{reservation_id}".encode(),
            response.data,
        )

        direct = self.post_admin(
            f"/admin/reservation/complete-rental-without-charge/{reservation_id}"
        )
        self.assertEqual(direct.status_code, 302)
        self.assertEqual(
            db.session.get(Reservation, reservation_id).status,
            "returned_pending_closure",
        )

    def test_cancelled_or_expired_reservation_cannot_be_cancelled_again(self):
        cancelled_id = self.create_cancellable_reservation("cancelled")
        expired_id = self.create_cancellable_reservation("expired")
        csrf_reservation_id = self.create_cancellable_reservation("pending_review")
        db.session.remove()

        csrf_path = f"/admin/reservation/cancel/{csrf_reservation_id}"
        cancelled_response = self.post_admin(
            f"/admin/reservation/cancel/{cancelled_id}", csrf_path=csrf_path
        )
        expired_response = self.post_admin(
            f"/admin/reservation/cancel/{expired_id}", csrf_path=csrf_path
        )

        self.assertEqual(cancelled_response.status_code, 302)
        self.assertEqual(expired_response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, cancelled_id).status, "cancelled")
        self.assertEqual(db.session.get(Reservation, expired_id).status, "expired")
