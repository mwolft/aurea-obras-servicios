"""Idempotent hourly processing for due security-deposit requests."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.extensions import db
from app.models import EmailOutbox, Payment, Reservation
from app.services.deposit_authorizations import (
    DepositAuthorizationError,
    start_or_recover_deposit_checkout,
)
from app.services.deposit_operations import (
    DEPOSIT_OPERATION_PENDING_REQUEST,
    OPERATIONAL_TIMEZONE,
    evaluate_deposit_operational_state,
    operational_now,
)
from app.services.email.outbox import deliver_outbox_emails
from app.services.email.rental import queue_deposit_automation_failure
from app.services.payment_domain import (
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_PAID,
    RESERVATION_STATUS_CONFIRMED,
)
from app.services.stripe_checkout import (
    ReservationPaymentNotFoundError,
    ReservationPaymentStateError,
    StripeCheckoutError,
    StripeConfigurationError,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DepositRequestAutomationResult:
    scanned: int = 0
    requested: int = 0
    skipped: int = 0
    failed: int = 0


def _latest_deposit(reservation_id: int) -> Payment | None:
    return db.session.execute(
        select(Payment)
        .where(
            Payment.reservation_id == reservation_id,
            Payment.purpose == PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
        )
        .order_by(Payment.id.desc())
    ).scalars().first()


def _has_paid_rental(reservation_id: int) -> bool:
    return db.session.execute(
        select(Payment.id).where(
            Payment.reservation_id == reservation_id,
            Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
            Payment.status == PAYMENT_STATUS_PAID,
        )
    ).scalar_one_or_none() is not None


def _request_email(payment: Payment | None) -> EmailOutbox | None:
    if payment is None:
        return None
    return db.session.execute(
        select(EmailOutbox).where(
            EmailOutbox.idempotency_key == f"deposit:{payment.id}:authorization_requested"
        )
    ).scalar_one_or_none()


def _is_due_for_automatic_request(reservation_id: int, current_time: datetime) -> bool:
    """Read the shared derived state before attempting the locked domain action."""
    reservation = db.session.get(Reservation, reservation_id)
    if reservation is None:
        return False
    # The automatic job is only a pre-delivery request.  A historical
    # confirmed reservation must be handled explicitly by Administration,
    # rather than receiving a new checkout after its planned start date.
    if reservation.start_date < current_time.astimezone(OPERATIONAL_TIMEZONE).date():
        return False
    payment = _latest_deposit(reservation.id)
    state = evaluate_deposit_operational_state(
        reservation,
        payment,
        _request_email(payment),
        rental_paid=_has_paid_rental(reservation.id),
        now=current_time,
    )
    return state.code == DEPOSIT_OPERATION_PENDING_REQUEST


def _record_failure(reservation_id: int, current_time: datetime) -> list[int]:
    """Persist one daily, sanitized Admin alert without touching the reservation."""
    outbox_ids: list[int] = []
    db.session.rollback()
    with db.session.begin():
        reservation = db.session.get(Reservation, reservation_id)
        if reservation is None:
            return outbox_ids
        alert = queue_deposit_automation_failure(
            db.session,
            reservation,
            occurrence_key=current_time.astimezone(OPERATIONAL_TIMEZONE).date().isoformat(),
        )
        if alert is not None:
            outbox_ids.append(alert.id)
    return outbox_ids


def request_due_deposit_authorizations(
    *,
    now: datetime | None = None,
) -> DepositRequestAutomationResult:
    """Request deposits that are due now, safely repeatable on every run.

    Only the existing start-or-recover domain service creates Checkout sessions.
    It locks the reservation and full deposit history, which prevents concurrent
    cron invocations or manual Admin use from creating competing authorizations.
    """
    current_time = operational_now(now)
    reservation_ids = list(
        db.session.execute(
            select(Reservation.id).where(
                Reservation.status == RESERVATION_STATUS_CONFIRMED,
                Reservation.deposit_amount_snapshot.is_not(None),
                Reservation.deposit_amount_snapshot > 0,
            )
        ).scalars()
    )
    db.session.rollback()

    requested = skipped = failed = 0
    for reservation_id in reservation_ids:
        try:
            due = _is_due_for_automatic_request(reservation_id, current_time)
        except Exception:
            logger.exception(
                "Automatic deposit eligibility check failed for reservation %s.", reservation_id
            )
            alert_ids = _record_failure(reservation_id, current_time)
            deliver_outbox_emails(alert_ids)
            failed += 1
            continue
        # The next operation owns a transaction and must not inherit the read
        # transaction opened by state evaluation.
        db.session.rollback()
        if not due:
            skipped += 1
            continue

        try:
            outbox_ids: list[int] = []
            start_or_recover_deposit_checkout(
                reservation_id,
                now=current_time,
                queue_request_email=True,
                outbox_ids=outbox_ids,
            )
        except (
            ReservationPaymentNotFoundError,
            ReservationPaymentStateError,
            DepositAuthorizationError,
            StripeConfigurationError,
            StripeCheckoutError,
        ):
            logger.exception(
                "Automatic deposit request failed for reservation %s.", reservation_id
            )
            alert_ids = _record_failure(reservation_id, current_time)
            deliver_outbox_emails(alert_ids)
            failed += 1
            continue

        deliver_outbox_emails(outbox_ids)
        requested += 1

    return DepositRequestAutomationResult(
        scanned=len(reservation_ids),
        requested=requested,
        skipped=skipped,
        failed=failed,
    )


__all__ = ["DepositRequestAutomationResult", "request_due_deposit_authorizations"]
