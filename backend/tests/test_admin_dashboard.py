import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "admin-dashboard-test-secret"
os.environ["APP_ENV"] = "development"

from app import create_app
from app.extensions import db
from app.models import EmailOutbox, Payment, Reservation, Tool, User
from app.services.admin_dashboard import get_dashboard_summary
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING_AUTHORIZATION,
)


class AdminDashboardTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()
        admin = User(name="Dashboard admin", email="dashboard-admin@example.com", is_admin=True)
        db.session.add(admin)
        db.session.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = admin.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def make_tool(name, *, published=True, available=True):
        tool = Tool(
            name=name,
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=Decimal("25.00"),
            pickup_available=True,
            delivery_available=True,
            delivery_price_per_km=Decimal("1.00"),
            is_published=published,
            is_available=available,
        )
        db.session.add(tool)
        db.session.commit()
        return tool

    @staticmethod
    def make_reservation(
        tool,
        start_date,
        end_date,
        status="confirmed",
        fulfillment_method="pickup",
        *,
        payment_expires_at=None,
    ):
        reservation = Reservation(
            tool_id=tool.id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            customer_name="Cliente Dashboard",
            customer_email="dashboard@example.com",
            customer_phone="600000000",
            terms_accepted=True,
            privacy_accepted=True,
            fulfillment_method=fulfillment_method,
            payment_expires_at=payment_expires_at,
        )
        db.session.add(reservation)
        db.session.commit()
        return reservation

    def test_dashboard_metrics_use_live_reservations_and_published_tool_configuration(self):
        current_date = date(2026, 8, 28)
        tool = self.make_tool("Hormigonera")
        self.make_tool("Desbrozadora", available=False)
        self.make_tool("No publicada", published=False)
        self.make_reservation(
            tool,
            current_date + timedelta(days=1),
            current_date + timedelta(days=3),
            "confirmed",
        )
        self.make_reservation(
            tool,
            current_date + timedelta(days=4),
            current_date + timedelta(days=4),
            "pending_review",
            "delivery",
        )
        self.make_reservation(
            tool,
            current_date + timedelta(days=5),
            current_date + timedelta(days=5),
            "pending_payment",
            payment_expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        self.make_reservation(
            tool,
            current_date + timedelta(days=6),
            current_date + timedelta(days=6),
            "pending_payment",
            payment_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        dashboard = get_dashboard_summary(today=current_date)

        self.assertEqual(dashboard.metrics.pending_reservations, 2)
        self.assertEqual(dashboard.metrics.upcoming_deliveries, 1)
        self.assertEqual(dashboard.metrics.upcoming_returns, 1)
        self.assertEqual((dashboard.metrics.available_tools, dashboard.metrics.published_tools), (1, 2))
        self.assertEqual(dashboard.pending_delivery_reviews, 1)

    def test_upcoming_activity_is_confirmed_only_chronological_and_limited(self):
        current_date = date(2026, 8, 28)
        tool = self.make_tool("Mini retroexcavadora")
        later = self.make_reservation(
            tool, current_date + timedelta(days=4), current_date + timedelta(days=5)
        )
        first = self.make_reservation(
            tool, current_date + timedelta(days=1), current_date + timedelta(days=2)
        )
        self.make_reservation(
            tool,
            current_date,
            current_date,
            "cancelled",
        )

        dashboard = get_dashboard_summary(today=current_date, activity_limit=3)

        self.assertEqual(
            [(item.operation, item.reservation_id) for item in dashboard.upcoming_activity],
            [("Entrega", first.id), ("Devolución", first.id), ("Entrega", later.id)],
        )

    def test_dashboard_renders_empty_state_and_real_admin_links(self):
        response = self.client.get("/admin/")
        content = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Resumen de la actividad de AUREA.", content)
        self.assertIn("No hay entregas ni devoluciones próximas.", content)
        self.assertIn("No hay gestiones pendientes.", content)
        for path in (
            "/admin/tool/new/",
            "/admin/calendar/",
            "/admin/toolimage/",
            "/admin/user/",
        ):
            with self.subTest(path=path):
                self.assertIn(path, content)

    def test_dashboard_activity_uses_reservation_detail_link(self):
        current_date = date.today()
        tool = self.make_tool("Desbrozadora")
        reservation = self.make_reservation(tool, current_date, current_date)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Desbrozadora", response.get_data(as_text=True))
        self.assertIn(f"/admin/reservation/details/?id={reservation.id}", response.get_data(as_text=True))

    def test_dashboard_separates_deposit_attention_from_customer_waiting(self):
        current_date = date.today()
        tool = self.make_tool("Miniexcavadora")
        attention = self.make_reservation(
            tool, current_date + timedelta(days=1), current_date + timedelta(days=2)
        )
        waiting = self.make_reservation(
            tool, current_date + timedelta(days=2), current_date + timedelta(days=3)
        )
        for reservation, status in (
            (attention, PAYMENT_STATUS_AUTHORIZED),
            (waiting, PAYMENT_STATUS_PENDING_AUTHORIZATION),
        ):
            reservation.deposit_amount_snapshot = Decimal("25.00")
            db.session.add(Payment(
                reservation_id=reservation.id,
                provider=PAYMENT_PROVIDER_STRIPE,
                purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
                status=PAYMENT_STATUS_PAID,
                amount=Decimal("20.00"),
                currency="eur",
                idempotency_key=f"rental-{reservation.id}",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            ))
            deposit = Payment(
                reservation_id=reservation.id,
                provider=PAYMENT_PROVIDER_STRIPE,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                status=status,
                amount=Decimal("25.00"),
                currency="eur",
                idempotency_key=f"deposit-{reservation.id}",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                capture_before=(
                    datetime.now(timezone.utc) + timedelta(hours=1)
                    if status == PAYMENT_STATUS_AUTHORIZED else None
                ),
            )
            db.session.add(deposit)
            db.session.flush()
            if status == PAYMENT_STATUS_PENDING_AUTHORIZATION:
                db.session.add(EmailOutbox(
                    event_type="deposit_authorization_requested",
                    reservation_id=reservation.id,
                    recipient="dashboard@example.com",
                    subject="Solicitud",
                    text_body="Texto",
                    html_body="<p>Texto</p>",
                    idempotency_key=f"deposit:{deposit.id}:authorization_requested",
                    status="sent",
                ))
        db.session.commit()

        dashboard = get_dashboard_summary(today=current_date)
        self.assertEqual([item.reservation_id for item in dashboard.deposit_attention], [attention.id])
        self.assertEqual([item.reservation_id for item in dashboard.deposit_waiting_customer], [waiting.id])
        response = self.client.get("/admin/")
        content = response.get_data(as_text=True)
        self.assertIn("Fianzas que requieren atención", content)
        self.assertIn("Esperando al cliente", content)
        self.assertIn(f"/admin/reservation/details/?id={attention.id}", content)
