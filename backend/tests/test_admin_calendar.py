import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "admin-calendar-test-secret"
os.environ["APP_ENV"] = "development"

from app import create_app
from app.extensions import db
from app.models import Reservation, Tool, ToolBlock, User
from app.services.admin_calendar import get_agenda_events, group_agenda_events


class AdminCalendarTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()
        admin = User(name="Calendar admin", email="calendar-admin@example.com", is_admin=True)
        db.session.add(admin)
        db.session.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = admin.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def make_tool(name):
        tool = Tool(
            name=name,
            category="Tests",
            daily_price=Decimal("10.00"),
            deposit_amount=Decimal("25.00"),
            pickup_available=True,
            delivery_available=False,
            is_published=True,
            is_available=True,
        )
        db.session.add(tool)
        db.session.commit()
        return tool

    @staticmethod
    def make_reservation(tool, start_date, end_date, status="confirmed", customer_name="Cliente Agenda"):
        reservation = Reservation(
            tool_id=tool.id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            customer_name=customer_name,
            customer_email="agenda@example.com",
            customer_phone="600000000",
            terms_accepted=True,
            privacy_accepted=True,
            fulfillment_method="pickup",
            payment_expires_at=(
                datetime.now(timezone.utc) + timedelta(minutes=10)
                if status == "pending_payment"
                else None
            ),
        )
        db.session.add(reservation)
        db.session.commit()
        return reservation

    @staticmethod
    def make_block(tool, start_date, end_date, reason="Mantenimiento"):
        block = ToolBlock(
            tool_id=tool.id,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
        )
        db.session.add(block)
        db.session.commit()
        return block

    def test_service_returns_no_events_for_empty_range(self):
        self.assertEqual(get_agenda_events(date(2026, 8, 1), date(2026, 8, 31)), [])

    def test_service_includes_reservations_blocks_and_partial_overlaps(self):
        tool = self.make_tool("Hormigonera")
        reservation = self.make_reservation(tool, date(2026, 8, 10), date(2026, 8, 12))
        block = self.make_block(tool, date(2026, 8, 12), date(2026, 8, 14), "Avería")
        outside = self.make_reservation(tool, date(2026, 8, 20), date(2026, 8, 21))

        events = get_agenda_events(date(2026, 8, 12), date(2026, 8, 15))

        self.assertEqual([(event.type, event.id) for event in events], [
            ("reservation", reservation.id),
            ("tool_block", block.id),
        ])
        self.assertNotIn(outside.id, [event.id for event in events])

    def test_service_filters_by_tool_and_orders_events_stably(self):
        other_tool = self.make_tool("Desbrozadora")
        tool = self.make_tool("Hormigonera")
        first = self.make_block(tool, date(2026, 8, 10), date(2026, 8, 10), "Uso interno")
        second = self.make_reservation(tool, date(2026, 8, 11), date(2026, 8, 12))
        self.make_reservation(other_tool, date(2026, 8, 9), date(2026, 8, 10))

        events = get_agenda_events(date(2026, 8, 1), date(2026, 8, 31), tool.id)
        groups = group_agenda_events(events)

        self.assertEqual([event.id for event in events], [first.id, second.id])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].tool_name, "Hormigonera")

    def test_expired_pending_payment_is_labeled_without_mutating_status(self):
        tool = self.make_tool("Hormigonera")
        reservation = self.make_reservation(tool, date(2026, 8, 10), date(2026, 8, 11), "pending_payment")
        reservation.payment_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()

        event = get_agenda_events(date(2026, 8, 10), date(2026, 8, 11))[0]

        self.assertEqual(event.status, "pending_payment")
        self.assertEqual(event.status_label, "Pago caducado")
        self.assertEqual(db.session.get(Reservation, reservation.id).status, "pending_payment")

    def test_cancelled_and_expired_reservations_remain_visible(self):
        tool = self.make_tool("Hormigonera")
        cancelled = self.make_reservation(tool, date(2026, 8, 10), date(2026, 8, 10), "cancelled")
        expired = self.make_reservation(tool, date(2026, 8, 11), date(2026, 8, 11), "expired")

        events = get_agenda_events(date(2026, 8, 1), date(2026, 8, 31))

        self.assertEqual(
            [(event.id, event.status_label) for event in events],
            [(cancelled.id, "Cancelada"), (expired.id, "Caducada")],
        )

    def test_admin_agenda_renders_filters_links_and_customer_only_in_admin(self):
        tool = self.make_tool("Hormigonera")
        reservation = self.make_reservation(tool, date(2026, 8, 10), date(2026, 8, 12))
        block = self.make_block(tool, date(2026, 8, 15), date(2026, 8, 16), "Mantenimiento")
        tool_id = tool.id
        reservation_id = reservation.id
        block_id = block.id
        db.session.remove()

        response = self.client.get(
            "/admin/calendar/",
            query_string={
                "start_date": "2026-08-01",
                "end_date": "2026-08-31",
                "tool_id": str(tool_id),
            },
        )
        public_response = self.client.get(f"/api/tools/{tool_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Cliente Agenda", response.data)
        self.assertIn(f"/admin/reservation/details/?id={reservation_id}".encode(), response.data)
        self.assertIn(f"/admin/toolblock/edit/?id={block_id}".encode(), response.data)
        self.assertNotIn(b"Cliente Agenda", public_response.data)

    def test_admin_agenda_handles_invalid_ranges_without_server_error(self):
        response = self.client.get(
            "/admin/calendar/",
            query_string={"start_date": "2026-08-20", "end_date": "2026-08-10"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"fecha de fin", response.data.lower())
