import os
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import inspect

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "rental-lifecycle-test-secret"
os.environ["APP_ENV"] = "development"

from app import create_app
from app.extensions import db
from app.models import Payment, Reservation, Tool, ToolBlock
from app.services.availability import is_tool_available
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CAPTURED_PARTIALLY,
    PAYMENT_STATUS_RELEASED,
    PAYMENT_STATUS_REQUIRES_REVIEW,
)
from app.services.rental_lifecycle import (
    RentalLifecycleError,
    calculate_overdue_days,
    complete_reservation_rental,
    is_reservation_overdue,
    mark_reservation_delivered,
    mark_reservation_returned,
)
from app.services.reservations import (
    ReservationCancellationError,
    ReservationUnavailableError,
    cancel_reservation,
    create_reservation,
)


class RentalLifecycleTestCase(unittest.TestCase):
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

    @staticmethod
    def now():
        return datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)

    def create_tool(self, *, deposit=Decimal("0.00")):
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

    def create_reservation(
        self,
        tool,
        *,
        status="confirmed",
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 12),
        deposit_snapshot=None,
    ):
        reservation = Reservation(
            tool_id=tool.id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            customer_name="Cliente de prueba",
            customer_email="cliente@example.com",
            customer_phone="600000000",
            terms_accepted=True,
            privacy_accepted=True,
            fulfillment_method="pickup",
            deposit_amount_snapshot=(tool.deposit_amount if deposit_snapshot is None else deposit_snapshot),
        )
        db.session.add(reservation)
        db.session.commit()
        return reservation

    def add_deposit_payment(self, reservation, status, *, capture_before=None):
        payment = Payment(
            reservation_id=reservation.id,
            provider=PAYMENT_PROVIDER_STRIPE,
            purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            status=status,
            amount=Decimal(reservation.deposit_amount_snapshot),
            currency="EUR",
            idempotency_key=uuid.uuid4().hex,
            expires_at=self.now() + timedelta(minutes=30),
            authorized_amount=(
                Decimal(reservation.deposit_amount_snapshot)
                if status == PAYMENT_STATUS_AUTHORIZED
                else None
            ),
            capture_before=capture_before,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def clean_session():
        """Mirror an HTTP request boundary before invoking a transactional service."""
        db.session.rollback()

    @staticmethod
    def reservation_id(reservation):
        return inspect(reservation).identity[0]

    def test_confirmed_reservation_with_zero_deposit_can_be_delivered(self):
        reservation = self.create_reservation(self.create_tool())

        self.clean_session()
        delivered = mark_reservation_delivered(
            self.reservation_id(reservation), "Entrega correcta", now=self.now()
        )

        self.assertEqual(delivered.status, "in_progress")
        self.assertEqual(
            delivered.delivered_at.replace(tzinfo=timezone.utc), self.now()
        )
        self.assertEqual(delivered.delivery_notes, "Entrega correcta")

    def test_confirmed_reservation_requires_a_current_authorized_deposit(self):
        tool = self.create_tool(deposit=Decimal("75.00"))
        reservation = self.create_reservation(tool)
        self.add_deposit_payment(
            reservation,
            PAYMENT_STATUS_AUTHORIZED,
            capture_before=self.now() + timedelta(days=2),
        )

        self.clean_session()
        self.assertEqual(mark_reservation_delivered(self.reservation_id(reservation), now=self.now()).status, "in_progress")

    def test_delivery_is_blocked_for_pending_expired_or_review_deposit(self):
        cases = (
            (PAYMENT_STATUS_REQUIRES_REVIEW, self.now() + timedelta(days=1)),
            (PAYMENT_STATUS_AUTHORIZATION_EXPIRED, self.now() - timedelta(minutes=1)),
            (PAYMENT_STATUS_AUTHORIZED, self.now() - timedelta(minutes=1)),
        )
        for status, capture_before in cases:
            with self.subTest(status=status):
                reservation = self.create_reservation(self.create_tool(deposit=Decimal("50.00")))
                self.add_deposit_payment(reservation, status, capture_before=capture_before)

                self.clean_session()
                with self.assertRaises(RentalLifecycleError):
                    mark_reservation_delivered(self.reservation_id(reservation), now=self.now())
                self.assertEqual(db.session.get(Reservation, self.reservation_id(reservation)).status, "confirmed")

    def test_delivery_cannot_be_recorded_twice(self):
        reservation = self.create_reservation(self.create_tool())
        self.clean_session()
        mark_reservation_delivered(self.reservation_id(reservation), now=self.now())

        self.clean_session()
        with self.assertRaises(RentalLifecycleError):
            mark_reservation_delivered(self.reservation_id(reservation), now=self.now())

    def test_active_rental_blocks_dates_after_the_contractual_end_and_public_endpoint_reports_it(self):
        tool = self.create_tool()
        reservation = self.create_reservation(
            tool, start_date=date(2026, 9, 1), end_date=date(2026, 9, 2)
        )
        self.clean_session()
        mark_reservation_delivered(self.reservation_id(reservation), now=self.now())

        self.assertFalse(is_tool_available(tool, date(2026, 10, 10), date(2026, 10, 11)))
        response = self.client.get(
            f"/api/tools/{tool.id}/unavailable-ranges",
            query_string={"start_date": "2026-10-01", "end_date": "2026-10-31"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["unavailable_ranges"], [])
        self.assertTrue(response.get_json()["active_rental"])
        self.assertNotIn("Cliente de prueba", response.get_data(as_text=True))

        tool_id = self.reservation_id(tool)
        db.session.rollback()
        with self.assertRaises(ReservationUnavailableError):
            create_reservation(
                tool_id,
                date(2026, 10, 10),
                date(2026, 10, 11),
                "Otro cliente",
                "otro@example.com",
                "611111111",
                True,
                True,
                "pickup",
                now=self.now(),
            )

    def test_return_ends_open_availability_block_and_does_not_create_a_tool_block(self):
        tool = self.create_tool()
        reservation = self.create_reservation(tool)
        self.clean_session()
        mark_reservation_delivered(self.reservation_id(reservation), now=self.now())

        self.clean_session()
        returned = mark_reservation_returned(
            self.reservation_id(reservation),
            self.now() + timedelta(hours=2),
            "Sin observaciones",
            "Pequeña incidencia anotada",
            now=self.now() + timedelta(hours=2),
        )

        self.assertEqual(returned.status, "returned_pending_closure")
        self.assertEqual(returned.return_notes, "Sin observaciones")
        self.assertEqual(returned.return_incident_notes, "Pequeña incidencia anotada")
        self.assertTrue(is_tool_available(tool, date(2026, 10, 10), date(2026, 10, 11)))
        self.assertEqual(ToolBlock.query.count(), 0)

    def test_return_can_only_be_recorded_once_for_an_active_rental(self):
        reservation = self.create_reservation(self.create_tool())
        self.clean_session()
        mark_reservation_delivered(self.reservation_id(reservation), now=self.now())
        self.clean_session()
        mark_reservation_returned(self.reservation_id(reservation), now=self.now())

        self.clean_session()
        with self.assertRaises(RentalLifecycleError):
            mark_reservation_returned(self.reservation_id(reservation), now=self.now())

    def test_overdue_days_start_after_20_00_in_madrid(self):
        reservation = self.create_reservation(
            self.create_tool(), end_date=date(2026, 9, 12)
        )
        self.assertEqual(
            calculate_overdue_days(reservation, datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc)),
            0,
        )
        self.assertTrue(
            is_reservation_overdue(reservation, datetime(2026, 9, 12, 19, 0, tzinfo=timezone.utc))
        )
        self.assertEqual(
            calculate_overdue_days(reservation, datetime(2026, 9, 13, 8, 0, tzinfo=timezone.utc)),
            1,
        )
        self.assertEqual(
            calculate_overdue_days(reservation, datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)),
            2,
        )

    def test_zero_deposit_rental_closes_after_return(self):
        reservation = self.create_reservation(self.create_tool())
        self.clean_session()
        mark_reservation_delivered(self.reservation_id(reservation), now=self.now())
        self.clean_session()
        mark_reservation_returned(self.reservation_id(reservation), now=self.now())

        self.clean_session()
        self.assertEqual(complete_reservation_rental(self.reservation_id(reservation)).status, "completed")

    def test_paid_deposit_final_states_allow_closure(self):
        for status in (PAYMENT_STATUS_RELEASED, PAYMENT_STATUS_CAPTURED_PARTIALLY, PAYMENT_STATUS_CAPTURED):
            with self.subTest(status=status):
                reservation = self.create_reservation(self.create_tool(deposit=Decimal("30.00")))
                reservation.status = "returned_pending_closure"
                reservation.returned_at = self.now()
                db.session.commit()
                self.add_deposit_payment(reservation, status)

                self.clean_session()
                self.assertEqual(complete_reservation_rental(self.reservation_id(reservation)).status, "completed")

    def test_unresolved_deposit_blocks_closure(self):
        for status in (PAYMENT_STATUS_AUTHORIZED, PAYMENT_STATUS_REQUIRES_REVIEW, PAYMENT_STATUS_AUTHORIZATION_EXPIRED):
            with self.subTest(status=status):
                reservation = self.create_reservation(self.create_tool(deposit=Decimal("30.00")))
                reservation.status = "returned_pending_closure"
                reservation.returned_at = self.now()
                db.session.commit()
                self.add_deposit_payment(reservation, status, capture_before=self.now() + timedelta(days=1))

                self.clean_session()
                with self.assertRaises(RentalLifecycleError):
                    complete_reservation_rental(self.reservation_id(reservation))

    def test_historical_null_deposit_is_not_inferred_for_delivery_or_closure(self):
        reservation = self.create_reservation(
            self.create_tool(deposit=Decimal("30.00")), deposit_snapshot=None
        )
        reservation.deposit_amount_snapshot = None
        db.session.commit()

        self.clean_session()
        with self.assertRaises(RentalLifecycleError):
            mark_reservation_delivered(self.reservation_id(reservation), now=self.now())

        reservation.status = "returned_pending_closure"
        reservation.returned_at = self.now()
        db.session.commit()
        self.clean_session()
        with self.assertRaises(RentalLifecycleError):
            complete_reservation_rental(self.reservation_id(reservation))

    def test_cancel_is_prohibited_after_delivery_and_through_closure(self):
        for status in ("in_progress", "returned_pending_closure", "completed"):
            with self.subTest(status=status):
                reservation = self.create_reservation(self.create_tool(), status=status)
                self.clean_session()
                with self.assertRaises(ReservationCancellationError):
                    cancel_reservation(self.reservation_id(reservation))
