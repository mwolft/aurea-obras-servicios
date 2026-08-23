import os
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
from app.models import Reservation, Tool
from app.services.availability import is_tool_available
from app.services.reservations import cancel_reservation, review_delivery_reservation


class ReservationAdminTestCase(unittest.TestCase):
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
            values["payment_expires_at"] = datetime.now(timezone.utc) + timedelta(minutes=15)
        values.update(overrides)
        reservation = Reservation(**values)
        db.session.add(reservation)
        db.session.commit()
        return reservation.id

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
            response = self.client.post(
                f"/admin/reservation/review-delivery/{reservation_id}",
                data={
                    "billable_km": "12.50",
                    "total_amount": "0.01",
                    "rental_amount": "0.01",
                },
            )

        self.assertEqual(response.status_code, 302)
        review_service.assert_called_once_with(reservation_id, Decimal("12.50"))
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
            timedelta(minutes=15).total_seconds(),
            delta=5,
        )

    def test_invalid_kilometres_do_not_change_reservation(self):
        reservation_id = self.create_pending_delivery_review()

        response = self.client.post(
            f"/admin/reservation/review-delivery/{reservation_id}",
            data={"billable_km": "-1"},
        )

        self.assertEqual(response.status_code, 302)
        reservation = db.session.get(Reservation, reservation_id)
        self.assertEqual(reservation.status, "pending_review")
        self.assertIsNone(reservation.billable_km)
        self.assertIsNone(reservation.total_amount)

    def test_stale_review_is_rejected_without_changes(self):
        reservation_id = self.create_pending_delivery_review(status="confirmed")
        db.session.remove()

        response = self.client.post(
            f"/admin/reservation/review-delivery/{reservation_id}",
            data={"billable_km": "12.50"},
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
            response = self.client.post(f"/admin/reservation/cancel/{reservation_id}")

        self.assertEqual(response.status_code, 302)
        cancellation_service.assert_called_once_with(reservation_id)
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

        pending_response = self.client.post(f"/admin/reservation/cancel/{pending_payment_id}")
        confirmed_response = self.client.post(f"/admin/reservation/cancel/{confirmed_id}")

        self.assertEqual(pending_response.status_code, 302)
        self.assertEqual(confirmed_response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, pending_payment_id).status, "cancelled")
        self.assertEqual(db.session.get(Reservation, confirmed_id).status, "cancelled")

    def test_cancelled_or_expired_reservation_cannot_be_cancelled_again(self):
        cancelled_id = self.create_cancellable_reservation("cancelled")
        expired_id = self.create_cancellable_reservation("expired")
        db.session.remove()

        cancelled_response = self.client.post(f"/admin/reservation/cancel/{cancelled_id}")
        expired_response = self.client.post(f"/admin/reservation/cancel/{expired_id}")

        self.assertEqual(cancelled_response.status_code, 302)
        self.assertEqual(expired_response.status_code, 302)
        self.assertEqual(db.session.get(Reservation, cancelled_id).status, "cancelled")
        self.assertEqual(db.session.get(Reservation, expired_id).status, "expired")
