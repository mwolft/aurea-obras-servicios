from datetime import date, datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Reservation, Tool, ToolBlock


RESERVATION_STATUS_LABELS = {
    "pending_review": "Pendiente de revisión",
    "pending_payment": "Pendiente de pago",
    "confirmed": "Confirmada",
    "cancelled": "Cancelada",
    "expired": "Caducada",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_pending_payment_expired(
    reservation: Reservation, now: datetime | None = None
) -> bool:
    """Return whether an unpaid checkout has passed its payment deadline.

    This is intentionally a read-only domain rule: callers must not mutate the
    stored status during a normal availability or account query.
    """
    if reservation.status != "pending_payment" or reservation.payment_expires_at is None:
        return False

    expiration = reservation.payment_expires_at
    if expiration.tzinfo is None:
        expiration = expiration.replace(tzinfo=timezone.utc)

    return expiration <= (utc_now() if now is None else now)


def reservation_status_label(reservation: Reservation, now: datetime | None = None) -> str:
    """Return the read-only, human-friendly operational status label."""
    if is_pending_payment_expired(reservation, now):
        return "Pago caducado"

    return RESERVATION_STATUS_LABELS.get(reservation.status, reservation.status)


def inclusive_date_range_conditions(model, start_date: date, end_date: date):
    """Build the shared inclusive date-overlap predicate for dated records."""
    return (
        model.start_date <= end_date,
        model.end_date >= start_date,
    )


def blocking_reservation_conditions(
    tool_id: int,
    start_date: date,
    end_date: date,
    now: datetime | None = None,
):
    current_time = utc_now() if now is None else now

    return (
        Reservation.tool_id == tool_id,
        *inclusive_date_range_conditions(Reservation, start_date, end_date),
        or_(
            Reservation.status == "confirmed",
            Reservation.status == "pending_review",
            and_(
                Reservation.status == "pending_payment",
                Reservation.payment_expires_at > current_time,
            ),
        ),
    )


def has_blocking_reservation(
    session: Session,
    tool_id: int,
    start_date: date,
    end_date: date,
    now: datetime | None = None,
) -> bool:
    blocking_reservation = session.execute(
        select(Reservation.id).where(
            *blocking_reservation_conditions(tool_id, start_date, end_date, now)
        ).limit(1)
    ).scalar_one_or_none()

    return blocking_reservation is not None


def has_tool_block(
    session: Session,
    tool_id: int,
    start_date: date,
    end_date: date,
    exclude_block_id: int | None = None,
) -> bool:
    """Return whether an operational block overlaps an inclusive date range."""
    conditions = [
        ToolBlock.tool_id == tool_id,
        *inclusive_date_range_conditions(ToolBlock, start_date, end_date),
    ]
    if exclude_block_id is not None:
        conditions.append(ToolBlock.id != exclude_block_id)

    return (
        session.execute(select(ToolBlock.id).where(*conditions).limit(1)).scalar_one_or_none()
        is not None
    )


def is_tool_available(
    tool: Tool,
    start_date: date,
    end_date: date,
    now: datetime | None = None,
) -> bool:
    """Return whether a tool can be rented for an inclusive date range."""
    if not tool.is_available:
        return False

    return not has_blocking_reservation(
        db.session, tool.id, start_date, end_date, now
    ) and not has_tool_block(db.session, tool.id, start_date, end_date)
