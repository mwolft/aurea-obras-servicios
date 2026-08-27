import os
import re
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "tool-block-test-secret"
os.environ["APP_ENV"] = "development"

from app import create_app
from app.extensions import db
from app.models import Reservation, Tool, ToolBlock, User
from app.services.availability import is_tool_available
from app.services.tool_blocks import create_tool_block, delete_tool_block


class ToolBlockTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()
        admin = User(name="Tool block admin", email="tool-block-admin@example.com", is_admin=True)
        db.session.add(admin)
        db.session.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = admin.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def admin_csrf_token(self):
        form_page = self.client.get("/admin/toolblock/")
        token = re.search(
            r'name="csrf_token"[^>]*value="([^"]+)"', form_page.get_data(as_text=True)
        )
        self.assertIsNotNone(token)
        return token.group(1)

    def post_admin(self, path, data):
        return self.client.post(path, data={**data, "csrf_token": self.admin_csrf_token()})

    def create_tool(self, **overrides):
        values = {
            "name": "Blocked tool",
            "category": "Tests",
            "daily_price": Decimal("10.00"),
            "deposit_amount": Decimal("25.00"),
            "pickup_available": True,
            "delivery_available": False,
            "is_published": True,
            "is_available": True,
        }
        values.update(overrides)
        tool = Tool(**values)
        db.session.add(tool)
        db.session.commit()
        return tool

    @staticmethod
    def create_block(tool, start_date, end_date, reason="Mantenimiento"):
        block = ToolBlock(
            tool_id=tool.id,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
        )
        db.session.add(block)
        db.session.commit()
        return block

    @staticmethod
    def create_reservation(tool, start_date, end_date, status="confirmed"):
        reservation = Reservation(
            tool_id=tool.id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            customer_name="Customer Test",
            customer_email="customer@example.com",
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
    def reservation_payload(**overrides):
        values = {
            "start_date": "2026-08-20",
            "end_date": "2026-08-22",
            "customer_name": "Customer Test",
            "customer_email": "customer@example.com",
            "customer_phone": "600000000",
            "terms_accepted": True,
            "privacy_accepted": True,
            "fulfillment_method": "pickup",
        }
        values.update(overrides)
        return values

    def availability_request(self, tool, start_date, end_date):
        return self.client.get(
            f"/api/tools/{tool.id}/availability",
            query_string={"start_date": start_date, "end_date": end_date},
        )

    def test_tool_block_blocks_all_inclusive_overlap_cases(self):
        tool = self.create_tool()
        self.create_block(tool, date(2026, 8, 10), date(2026, 8, 12))

        for requested_start, requested_end in (
            ("2026-08-10", "2026-08-12"),
            ("2026-08-12", "2026-08-15"),
            ("2026-08-08", "2026-08-10"),
            ("2026-08-09", "2026-08-13"),
        ):
            with self.subTest(start=requested_start, end=requested_end):
                self.assertFalse(
                    self.availability_request(tool, requested_start, requested_end).get_json()[
                        "available"
                    ]
                )

        self.assertTrue(
            self.availability_request(tool, "2026-08-13", "2026-08-15").get_json()["available"]
        )

    def test_deleting_block_releases_availability(self):
        tool = self.create_tool()
        tool_id = tool.id
        db.session.remove()
        block = create_tool_block(tool_id, date(2026, 8, 10), date(2026, 8, 12), "Avería")
        block_id = block.id
        db.session.remove()

        self.assertFalse(is_tool_available(db.session.get(Tool, tool_id), date(2026, 8, 10), date(2026, 8, 12)))
        db.session.rollback()
        delete_tool_block(block_id)
        db.session.remove()

        self.assertTrue(is_tool_available(db.session.get(Tool, tool_id), date(2026, 8, 10), date(2026, 8, 12)))

    def test_reservation_overlapping_block_returns_conflict_but_outside_range_is_created(self):
        tool = self.create_tool()
        self.create_block(tool, date(2026, 8, 20), date(2026, 8, 22))
        tool_id = tool.id
        db.session.remove()

        blocked_response = self.client.post(
            f"/api/tools/{tool_id}/reservations", json=self.reservation_payload()
        )
        outside_response = self.client.post(
            f"/api/tools/{tool_id}/reservations",
            json=self.reservation_payload(start_date="2026-08-23", end_date="2026-08-24"),
        )

        self.assertEqual(blocked_response.status_code, 409)
        self.assertEqual(outside_response.status_code, 201)

    def test_admin_creates_edits_and_deletes_block(self):
        tool = self.create_tool()
        tool_id = tool.id
        db.session.remove()

        create_response = self.post_admin(
            "/admin/toolblock/new/",
            data={
                "tool": str(tool_id),
                "start_date": "2026-08-20",
                "end_date": "2026-08-22",
                "reason": "Uso interno",
            },
        )
        self.assertEqual(create_response.status_code, 302)
        block = ToolBlock.query.one()
        block_id = block.id
        self.assertEqual(block.reason, "Uso interno")
        db.session.remove()

        edit_response = self.post_admin(
            f"/admin/toolblock/edit/?id={block_id}",
            data={
                "tool": str(tool_id),
                "start_date": "2026-08-21",
                "end_date": "2026-08-23",
                "reason": "Uso interno actualizado",
            },
        )
        self.assertEqual(edit_response.status_code, 302)
        block = db.session.get(ToolBlock, block_id)
        self.assertEqual(block.start_date, date(2026, 8, 21))
        self.assertEqual(block.reason, "Uso interno actualizado")
        db.session.remove()

        delete_response = self.post_admin(
            f"/admin/toolblock/delete/?id={block_id}", {"id": str(block_id)}
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertIsNone(db.session.get(ToolBlock, block_id))
        self.assertTrue(is_tool_available(db.session.get(Tool, tool_id), date(2026, 8, 21), date(2026, 8, 23)))

    def test_admin_rejects_invalid_or_conflicting_blocks(self):
        tool = self.create_tool()
        tool_id = tool.id
        self.create_reservation(tool, date(2026, 8, 20), date(2026, 8, 22))
        db.session.remove()

        conflicting_reservation = self.post_admin(
            "/admin/toolblock/new/",
            data={
                "tool": str(tool_id),
                "start_date": "2026-08-20",
                "end_date": "2026-08-22",
                "reason": "Mantenimiento",
            },
        )
        self.assertEqual(conflicting_reservation.status_code, 200)
        self.assertEqual(ToolBlock.query.count(), 0)

        db.session.remove()
        invalid_range = self.post_admin(
            "/admin/toolblock/new/",
            data={
                "tool": str(tool_id),
                "start_date": "2026-08-23",
                "end_date": "2026-08-20",
                "reason": "Mantenimiento",
            },
        )
        self.assertEqual(invalid_range.status_code, 200)
        self.assertEqual(ToolBlock.query.count(), 0)

        db.session.remove()
        missing_reason = self.post_admin(
            "/admin/toolblock/new/",
            data={
                "tool": str(tool_id),
                "start_date": "2026-08-23",
                "end_date": "2026-08-24",
                "reason": " ",
            },
        )
        self.assertEqual(missing_reason.status_code, 200)
        self.assertEqual(ToolBlock.query.count(), 0)

    def test_admin_tool_block_form_requires_csrf_token(self):
        tool = self.create_tool()

        response = self.client.post(
            "/admin/toolblock/new/",
            data={
                "tool": str(tool.id),
                "start_date": "2026-08-23",
                "end_date": "2026-08-24",
                "reason": "Mantenimiento",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ToolBlock.query.count(), 0)

    def test_admin_rejects_overlapping_tool_blocks(self):
        tool = self.create_tool()
        tool_id = tool.id
        block = self.create_block(tool, date(2026, 8, 20), date(2026, 8, 22))
        block_id = block.id
        db.session.remove()

        response = self.post_admin(
            "/admin/toolblock/new/",
            data={
                "tool": str(tool_id),
                "start_date": "2026-08-22",
                "end_date": "2026-08-24",
                "reason": "Segundo bloqueo",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ToolBlock.query.count(), 1)
        self.assertEqual(ToolBlock.query.one().id, block_id)

    def test_admin_list_is_available_with_expected_fields(self):
        response = self.client.get("/admin/toolblock/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Herramienta", response.data)
        self.assertIn(b"Fecha inicio", response.data)
        self.assertIn(b"Fecha fin", response.data)
        self.assertIn(b"Motivo", response.data)
