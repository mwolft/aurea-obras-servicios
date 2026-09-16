"""Derived, read-only operational state for security-deposit follow-up.

Financial ``Payment.status`` remains the source of truth for provider events.
This module only turns existing reservation, payment and email-outbox data into
an operational queue that Administration (and a future scheduler) can share.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models import EmailOutbox, Payment, Reservation
from app.models.email_outbox import EMAIL_OUTBOX_STATUS_FAILED, EMAIL_OUTBOX_STATUS_SENT
from app.services.payment_domain import (
    PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
    PAYMENT_STATUS_AUTHORIZATION_FAILED,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_PENDING_AUTHORIZATION,
    PAYMENT_STATUS_REQUIRES_REVIEW,
    RESERVATION_STATUS_CONFIRMED,
)


OPERATIONAL_TIMEZONE = ZoneInfo("Europe/Madrid")
DEPOSIT_REQUEST_LEAD_TIME = timedelta(hours=48)
DEPOSIT_RETURN_MARGIN = timedelta(hours=24)
DEPOSIT_RETURN_CUTOFF = time(hour=20)
LONG_RENTAL_DAYS = 6

DEPOSIT_OPERATION_NOT_APPLICABLE = "not_applicable"
DEPOSIT_OPERATION_NOT_DUE = "not_due"
DEPOSIT_OPERATION_PENDING_REQUEST = "pending_request"
DEPOSIT_OPERATION_AWAITING_CUSTOMER = "awaiting_customer"
DEPOSIT_OPERATION_REQUEST_EXPIRED = "request_expired"
DEPOSIT_OPERATION_EMAIL_FAILED = "email_failed"
DEPOSIT_OPERATION_AUTHORIZED_SUFFICIENT = "authorized_sufficient"
DEPOSIT_OPERATION_AUTHORIZED_INSUFFICIENT = "authorized_insufficient"
DEPOSIT_OPERATION_REAUTHORIZE = "reauthorize"
DEPOSIT_OPERATION_REQUIRES_REVIEW = "requires_review"
DEPOSIT_OPERATION_AUTOMATION_FAILED = "automation_failed"


@dataclass(frozen=True)
class DepositOperationalState:
    code: str
    label: str
    requires_attention: bool = False
    awaiting_customer: bool = False
    delivery_soon: bool = False
    long_rental: bool = False
    coverage_sufficient: bool | None = None


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def operational_now(now: datetime | None = None) -> datetime:
    """Return a timezone-aware instant without relying on the server locale."""
    current = datetime.now(timezone.utc) if now is None else now
    return _as_utc(current) or datetime.now(timezone.utc)


def request_due_at(reservation: Reservation) -> datetime:
    """The reusable 48-hour rule, anchored to the local start-date boundary."""
    delivery_start = datetime.combine(reservation.start_date, time.min, OPERATIONAL_TIMEZONE)
    return delivery_start - DEPOSIT_REQUEST_LEAD_TIME


def planned_return_cutoff(reservation: Reservation) -> datetime:
    """Return the local operational return cutoff (20:00) as an instant."""
    return datetime.combine(reservation.end_date, DEPOSIT_RETURN_CUTOFF, OPERATIONAL_TIMEZONE)


def rental_days(reservation: Reservation) -> int:
    return (reservation.end_date - reservation.start_date).days + 1


def deposit_capture_covers_return(reservation: Reservation, payment: Payment) -> bool:
    capture_before = _as_utc(payment.capture_before)
    if capture_before is None:
        return False
    required_until = planned_return_cutoff(reservation) + DEPOSIT_RETURN_MARGIN
    return capture_before >= required_until.astimezone(timezone.utc)


def _delivery_is_soon(reservation: Reservation, now: datetime) -> bool:
    today = now.astimezone(OPERATIONAL_TIMEZONE).date()
    return reservation.start_date <= today + timedelta(days=1)


def _not_applicable(reservation: Reservation, rental_paid: bool) -> bool:
    return (
        reservation.status != RESERVATION_STATUS_CONFIRMED
        or not rental_paid
        or reservation.deposit_amount_snapshot is None
        or Decimal(reservation.deposit_amount_snapshot) <= 0
    )


def evaluate_deposit_operational_state(
    reservation: Reservation,
    payment: Payment | None,
    request_email: EmailOutbox | None,
    *,
    rental_paid: bool,
    automation_failed: bool = False,
    now: datetime | None = None,
) -> DepositOperationalState:
    """Classify one reservation without mutating financial state.

    A Stripe reconciliation remains the responsibility of the action that
    creates/replaces an authorization.  This function deliberately uses local
    persisted facts so it is safe for the dashboard and future scheduled jobs.
    """
    current = operational_now(now)
    if _not_applicable(reservation, rental_paid):
        return DepositOperationalState(DEPOSIT_OPERATION_NOT_APPLICABLE, "No aplica")

    long_rental = rental_days(reservation) >= LONG_RENTAL_DAYS
    delivery_soon = _delivery_is_soon(reservation, current)
    common = {"delivery_soon": delivery_soon, "long_rental": long_rental}

    if automation_failed:
        return DepositOperationalState(
            DEPOSIT_OPERATION_AUTOMATION_FAILED,
            "La solicitud automática requiere revisión",
            requires_attention=True,
            **common,
        )

    if payment is None:
        if current < request_due_at(reservation).astimezone(timezone.utc):
            return DepositOperationalState(
                DEPOSIT_OPERATION_NOT_DUE,
                "No toca solicitar todavía",
                **common,
            )
        return DepositOperationalState(
            DEPOSIT_OPERATION_PENDING_REQUEST,
            "Pendiente de solicitar",
            requires_attention=True,
            **common,
        )

    if payment.status == PAYMENT_STATUS_REQUIRES_REVIEW:
        return DepositOperationalState(
            DEPOSIT_OPERATION_REQUIRES_REVIEW,
            "Requiere revisión",
            requires_attention=True,
            **common,
        )

    if payment.status in {
        PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
        PAYMENT_STATUS_AUTHORIZATION_FAILED,
    }:
        return DepositOperationalState(
            DEPOSIT_OPERATION_REAUTHORIZE,
            "Caducada antes de entrega · requiere reautorización",
            requires_attention=True,
            **common,
        )

    if payment.status == PAYMENT_STATUS_AUTHORIZED:
        capture_before = _as_utc(payment.capture_before)
        if capture_before is None or capture_before <= current:
            return DepositOperationalState(
                DEPOSIT_OPERATION_REAUTHORIZE,
                "Caducada antes de entrega · requiere reautorización",
                requires_attention=True,
                **common,
            )
        covers_return = deposit_capture_covers_return(reservation, payment)
        if not covers_return:
            return DepositOperationalState(
                DEPOSIT_OPERATION_AUTHORIZED_INSUFFICIENT,
                "Autorizada, pero con vigencia insuficiente para la devolución",
                requires_attention=True,
                coverage_sufficient=False,
                **common,
            )
        return DepositOperationalState(
            DEPOSIT_OPERATION_AUTHORIZED_SUFFICIENT,
            "Autorizada y con cobertura suficiente",
            coverage_sufficient=True,
            **common,
        )

    if payment.status == PAYMENT_STATUS_PENDING_AUTHORIZATION:
        checkout_expires_at = _as_utc(payment.expires_at)
        if checkout_expires_at is None or checkout_expires_at <= current:
            return DepositOperationalState(
                DEPOSIT_OPERATION_REQUEST_EXPIRED,
                "Solicitud vencida",
                requires_attention=True,
                **common,
            )
        if request_email is not None and request_email.status == EMAIL_OUTBOX_STATUS_FAILED:
            return DepositOperationalState(
                DEPOSIT_OPERATION_EMAIL_FAILED,
                "Email fallido",
                requires_attention=True,
                **common,
            )
        if request_email is not None and request_email.status == EMAIL_OUTBOX_STATUS_SENT:
            return DepositOperationalState(
                DEPOSIT_OPERATION_AWAITING_CUSTOMER,
                "Esperando autorización del cliente",
                awaiting_customer=True,
                **common,
            )
        return DepositOperationalState(
            DEPOSIT_OPERATION_PENDING_REQUEST,
            "Pendiente de solicitar",
            requires_attention=True,
            **common,
        )

    return DepositOperationalState(DEPOSIT_OPERATION_NOT_APPLICABLE, "No aplica")


__all__ = [
    "DEPOSIT_REQUEST_LEAD_TIME",
    "DEPOSIT_RETURN_MARGIN",
    "LONG_RENTAL_DAYS",
    "DEPOSIT_OPERATION_NOT_DUE",
    "DEPOSIT_OPERATION_PENDING_REQUEST",
    "DEPOSIT_OPERATION_AWAITING_CUSTOMER",
    "DEPOSIT_OPERATION_REQUEST_EXPIRED",
    "DEPOSIT_OPERATION_EMAIL_FAILED",
    "DEPOSIT_OPERATION_AUTHORIZED_SUFFICIENT",
    "DEPOSIT_OPERATION_AUTHORIZED_INSUFFICIENT",
    "DEPOSIT_OPERATION_REAUTHORIZE",
    "DEPOSIT_OPERATION_REQUIRES_REVIEW",
    "DEPOSIT_OPERATION_AUTOMATION_FAILED",
    "DepositOperationalState",
    "deposit_capture_covers_return",
    "evaluate_deposit_operational_state",
    "operational_now",
    "planned_return_cutoff",
    "request_due_at",
    "rental_days",
]
