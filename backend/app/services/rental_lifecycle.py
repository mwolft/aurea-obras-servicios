"""Operational lifecycle for physical rental handover, return, and closure."""

from datetime import datetime, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Payment, Reservation
from app.services.availability import utc_now
from app.services.payment_domain import (
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CAPTURED_PARTIALLY,
    PAYMENT_STATUS_RELEASED,
    RESERVATION_STATUS_COMPLETED,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_IN_PROGRESS,
    RESERVATION_STATUS_RETURNED_PENDING_CLOSURE,
)
from app.services.email.rental import (
    queue_reservation_completed,
    queue_reservation_delivered,
    queue_reservation_returned,
)


OPERATIONAL_TIMEZONE = ZoneInfo("Europe/Madrid")
RETURN_DEADLINE = time(20, 0)
MAX_OPERATION_NOTE_LENGTH = 4_000


class RentalLifecycleError(RuntimeError):
    """Raised when a physical rental operation cannot make its transition."""


class ReservationOperationalNotFoundError(RentalLifecycleError):
    """Raised when the requested reservation does not exist."""


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _normalize_notes(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RentalLifecycleError(f"{field_name} debe ser texto.")
    normalized = value.strip()
    if len(normalized) > MAX_OPERATION_NOTE_LENGTH:
        raise RentalLifecycleError(f"{field_name} no puede superar {MAX_OPERATION_NOTE_LENGTH} caracteres.")
    return normalized or None


def calculate_overdue_days(
    reservation: Reservation,
    at: datetime | None = None,
) -> int:
    """Return whole natural calendar days started after the 20:00 due time.

    A return on the next local calendar day counts as one extra day even when it
    happens in the morning. This is informational only: it never changes the
    existing rental quote or creates a charge.
    """
    effective_time = _as_utc(reservation.returned_at or at or utc_now()).astimezone(
        OPERATIONAL_TIMEZONE
    )
    deadline = datetime.combine(
        reservation.end_date, RETURN_DEADLINE, tzinfo=OPERATIONAL_TIMEZONE
    )
    if effective_time <= deadline:
        return 0
    return max(0, (effective_time.date() - deadline.date()).days)


def is_reservation_overdue(reservation: Reservation, at: datetime | None = None) -> bool:
    effective_time = _as_utc(reservation.returned_at or at or utc_now()).astimezone(
        OPERATIONAL_TIMEZONE
    )
    deadline = datetime.combine(
        reservation.end_date, RETURN_DEADLINE, tzinfo=OPERATIONAL_TIMEZONE
    )
    return effective_time > deadline


def _latest_deposit_payment(session: Session, reservation_id: int) -> Payment | None:
    return session.execute(
        select(Payment)
        .where(
            Payment.reservation_id == reservation_id,
            Payment.purpose == PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
        )
        .order_by(Payment.id.desc())
        .with_for_update()
    ).scalars().first()


def _deposit_is_valid_for_handover(
    session: Session, reservation: Reservation, now: datetime
) -> bool:
    if reservation.deposit_amount_snapshot is None:
        # Historical reservations have no contractual snapshot; never infer one
        # from the current Tool configuration.
        raise RentalLifecycleError(
            "La reserva no tiene una fianza contractual histórica; requiere revisión manual."
        )
    if Decimal(reservation.deposit_amount_snapshot) == 0:
        return True

    payment = _latest_deposit_payment(session, reservation.id)
    if payment is None or payment.status != PAYMENT_STATUS_AUTHORIZED:
        return False
    if payment.capture_before is None:
        return False
    return _as_utc(payment.capture_before) > now


def mark_reservation_delivered(
    reservation_id: int,
    delivery_notes: str | None = None,
    *,
    session: Session | None = None,
    now: datetime | None = None,
    outbox_ids: list[int] | None = None,
) -> Reservation:
    """Record physical handover after server-side state and deposit checks."""
    operation_session = db.session if session is None else session
    current_time = _as_utc(now or utc_now())
    notes = _normalize_notes(delivery_notes, "Las notas de entrega")

    with operation_session.begin():
        reservation = operation_session.execute(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        ).scalar_one_or_none()
        if reservation is None:
            raise ReservationOperationalNotFoundError
        if reservation.status != RESERVATION_STATUS_CONFIRMED:
            raise RentalLifecycleError("Solo una reserva confirmada puede marcarse como entregada.")
        if not _deposit_is_valid_for_handover(operation_session, reservation, current_time):
            raise RentalLifecycleError("La fianza debe estar autorizada y vigente antes de la entrega.")

        reservation.delivered_at = current_time
        reservation.delivery_notes = notes
        reservation.status = RESERVATION_STATUS_IN_PROGRESS
        email = queue_reservation_delivered(operation_session, reservation)
        if outbox_ids is not None and email is not None:
            outbox_ids.append(email.id)

    return reservation


def mark_reservation_returned(
    reservation_id: int,
    returned_at: datetime | None = None,
    return_notes: str | None = None,
    return_incident_notes: str | None = None,
    *,
    session: Session | None = None,
    now: datetime | None = None,
    outbox_ids: list[int] | None = None,
) -> Reservation:
    """Record physical return without resolving the separate deposit lifecycle."""
    operation_session = db.session if session is None else session
    current_time = _as_utc(now or utc_now())
    actual_return = _as_utc(returned_at or current_time)
    notes = _normalize_notes(return_notes, "Las notas de devolución")
    incident_notes = _normalize_notes(return_incident_notes, "Las notas de incidencia")

    if actual_return > current_time:
        raise RentalLifecycleError("La fecha de devolución no puede estar en el futuro.")

    with operation_session.begin():
        reservation = operation_session.execute(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        ).scalar_one_or_none()
        if reservation is None:
            raise ReservationOperationalNotFoundError
        if reservation.status != RESERVATION_STATUS_IN_PROGRESS:
            raise RentalLifecycleError("Solo un alquiler en curso puede marcarse como devuelto.")
        if reservation.delivered_at is not None and actual_return < _as_utc(reservation.delivered_at):
            raise RentalLifecycleError("La devolución no puede ser anterior a la entrega.")

        reservation.returned_at = actual_return
        reservation.return_notes = notes
        reservation.return_incident_notes = incident_notes
        reservation.status = RESERVATION_STATUS_RETURNED_PENDING_CLOSURE
        email = queue_reservation_returned(operation_session, reservation)
        if outbox_ids is not None and email is not None:
            outbox_ids.append(email.id)

    return reservation


def _deposit_is_resolved_for_closure(session: Session, reservation: Reservation) -> bool:
    if reservation.deposit_amount_snapshot is None:
        raise RentalLifecycleError(
            "La reserva no tiene una fianza contractual histórica; requiere revisión manual."
        )
    if Decimal(reservation.deposit_amount_snapshot) == 0:
        return True
    payment = _latest_deposit_payment(session, reservation.id)
    return payment is not None and payment.status in {
        PAYMENT_STATUS_RELEASED,
        PAYMENT_STATUS_CAPTURED_PARTIALLY,
        PAYMENT_STATUS_CAPTURED,
    }


def complete_reservation_rental(
    reservation_id: int, *, session: Session | None = None, outbox_ids: list[int] | None = None
) -> Reservation:
    """Close a returned rental only after its deposit has reached a final state."""
    operation_session = db.session if session is None else session
    with operation_session.begin():
        reservation = operation_session.execute(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        ).scalar_one_or_none()
        if reservation is None:
            raise ReservationOperationalNotFoundError
        if reservation.status != RESERVATION_STATUS_RETURNED_PENDING_CLOSURE:
            raise RentalLifecycleError("Solo una devolución pendiente de cierre puede completarse.")
        if reservation.returned_at is None:
            raise RentalLifecycleError("La herramienta debe estar devuelta antes de cerrar el alquiler.")
        if not _deposit_is_resolved_for_closure(operation_session, reservation):
            raise RentalLifecycleError("La fianza todavía no está resuelta.")
        reservation.status = RESERVATION_STATUS_COMPLETED
        email = queue_reservation_completed(operation_session, reservation)
        if outbox_ids is not None and email is not None:
            outbox_ids.append(email.id)

    return reservation
