import os
import threading
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from dotenv import dotenv_values
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from app import create_app
from app.extensions import db
from app.models import Reservation, Tool, ToolBlock
from app.services.reservations import ReservationUnavailableError, create_reservation
from app.services.tool_blocks import ToolBlockConflictError, create_tool_block


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
ENVIRONMENT = dotenv_values(ENV_PATH)
TEST_DATABASE_URL = ENVIRONMENT.get("TEST_DATABASE_URL")
DEVELOPMENT_DATABASE_URL = ENVIRONMENT.get("DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured.")
class PostgreSQLReservationConcurrencyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if TEST_DATABASE_URL == DEVELOPMENT_DATABASE_URL:
            raise RuntimeError("TEST_DATABASE_URL must be isolated from DATABASE_URL.")

        cls.environment = patch.dict(
            os.environ,
            {
                "DATABASE_URL": TEST_DATABASE_URL,
                "SECRET_KEY": "postgresql-concurrency-test-secret",
                "APP_ENV": "production",
                "FRONTEND_ORIGIN": "https://www.example.test",
                "CLOUDINARY_CLOUD_NAME": "test-cloud",
                "CLOUDINARY_API_KEY": "test-key",
                "CLOUDINARY_API_SECRET": "test-secret",
            },
            clear=False,
        )
        cls.environment.start()
        cls.app = create_app()
        cls.context = cls.app.app_context()
        cls.context.push()

        if db.engine.dialect.name != "postgresql":
            raise RuntimeError("The concurrency test requires PostgreSQL.")

        cls.Session = sessionmaker(bind=db.engine, expire_on_commit=False)

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        cls.context.pop()
        cls.environment.stop()

    def test_only_one_concurrent_reservation_is_created(self):
        tool_id = None
        try:
            setup_session = self.Session()
            try:
                with setup_session.begin():
                    tool = Tool(
                        name="PostgreSQL concurrency test tool",
                        category="Tests",
                        daily_price=Decimal("10.00"),
                        deposit_amount=Decimal("25.00"),
                        pickup_available=True,
                        delivery_available=False,
                        is_published=True,
                        is_available=True,
                    )
                    setup_session.add(tool)
                    setup_session.flush()
                    tool_id = tool.id
            finally:
                setup_session.close()

            start_barrier = threading.Barrier(3, timeout=15)
            outcomes = []
            worker_errors = []
            outcomes_lock = threading.Lock()

            def attempt_reservation():
                session = self.Session()
                try:
                    start_barrier.wait()
                    reservation = create_reservation(
                        tool_id,
                        date(2026, 8, 20),
                        date(2026, 8, 22),
                        "Concurrency Test",
                        "concurrency@example.com",
                        "600000000",
                        True,
                        True,
                        "pickup",
                        session=session,
                    )
                    with outcomes_lock:
                        outcomes.append(("created", reservation.id))
                except ReservationUnavailableError:
                    with outcomes_lock:
                        outcomes.append(("conflict", None))
                except Exception as error:
                    with outcomes_lock:
                        worker_errors.append(error)
                finally:
                    session.close()

            first_worker = threading.Thread(target=attempt_reservation)
            second_worker = threading.Thread(target=attempt_reservation)
            first_worker.start()
            second_worker.start()
            start_barrier.wait()
            first_worker.join(timeout=15)
            second_worker.join(timeout=15)

            self.assertFalse(first_worker.is_alive())
            self.assertFalse(second_worker.is_alive())
            self.assertEqual(worker_errors, [])
            self.assertEqual([outcome for outcome, _ in outcomes].count("created"), 1)
            self.assertEqual([outcome for outcome, _ in outcomes].count("conflict"), 1)

            verification_session = self.Session()
            try:
                pending_reservations = verification_session.execute(
                    select(Reservation).where(
                        Reservation.tool_id == tool_id,
                        Reservation.status == "pending_payment",
                    )
                ).scalars().all()
                self.assertEqual(len(pending_reservations), 1)
            finally:
                verification_session.close()
        finally:
            if tool_id is not None:
                cleanup_session = self.Session()
                try:
                    with cleanup_session.begin():
                        cleanup_session.execute(delete(Reservation).where(Reservation.tool_id == tool_id))
                        cleanup_session.execute(delete(ToolBlock).where(ToolBlock.tool_id == tool_id))
                        cleanup_session.execute(delete(Tool).where(Tool.id == tool_id))
                finally:
                    cleanup_session.close()

    def test_reservation_and_tool_block_cannot_be_created_for_the_same_dates(self):
        tool_id = None
        try:
            setup_session = self.Session()
            try:
                with setup_session.begin():
                    tool = Tool(
                        name="PostgreSQL block concurrency test tool",
                        category="Tests",
                        daily_price=Decimal("10.00"),
                        deposit_amount=Decimal("25.00"),
                        pickup_available=True,
                        delivery_available=False,
                        is_published=True,
                        is_available=True,
                    )
                    setup_session.add(tool)
                    setup_session.flush()
                    tool_id = tool.id
            finally:
                setup_session.close()

            start_barrier = threading.Barrier(3, timeout=15)
            outcomes = []
            worker_errors = []
            outcomes_lock = threading.Lock()

            def attempt_reservation():
                session = self.Session()
                try:
                    start_barrier.wait()
                    create_reservation(
                        tool_id,
                        date(2026, 8, 20),
                        date(2026, 8, 22),
                        "Concurrency Test",
                        "concurrency@example.com",
                        "600000000",
                        True,
                        True,
                        "pickup",
                        session=session,
                    )
                    with outcomes_lock:
                        outcomes.append("reservation")
                except ReservationUnavailableError:
                    with outcomes_lock:
                        outcomes.append("reservation_conflict")
                except Exception as error:
                    with outcomes_lock:
                        worker_errors.append(error)
                finally:
                    session.close()

            def attempt_block():
                session = self.Session()
                try:
                    start_barrier.wait()
                    create_tool_block(
                        tool_id,
                        date(2026, 8, 20),
                        date(2026, 8, 22),
                        "Mantenimiento de concurrencia",
                        session=session,
                    )
                    with outcomes_lock:
                        outcomes.append("block")
                except ToolBlockConflictError:
                    with outcomes_lock:
                        outcomes.append("block_conflict")
                except Exception as error:
                    with outcomes_lock:
                        worker_errors.append(error)
                finally:
                    session.close()

            reservation_worker = threading.Thread(target=attempt_reservation)
            block_worker = threading.Thread(target=attempt_block)
            reservation_worker.start()
            block_worker.start()
            start_barrier.wait()
            reservation_worker.join(timeout=15)
            block_worker.join(timeout=15)

            self.assertFalse(reservation_worker.is_alive())
            self.assertFalse(block_worker.is_alive())
            self.assertEqual(worker_errors, [])
            self.assertEqual(len(outcomes), 2)
            self.assertEqual(sum(outcome in {"reservation", "block"} for outcome in outcomes), 1)
            self.assertEqual(sum(outcome.endswith("conflict") for outcome in outcomes), 1)
        finally:
            if tool_id is not None:
                cleanup_session = self.Session()
                try:
                    with cleanup_session.begin():
                        cleanup_session.execute(delete(Reservation).where(Reservation.tool_id == tool_id))
                        cleanup_session.execute(delete(ToolBlock).where(ToolBlock.tool_id == tool_id))
                        cleanup_session.execute(delete(Tool).where(Tool.id == tool_id))
                finally:
                    cleanup_session.close()
