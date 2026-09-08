from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Reservation, Tool, ToolBlock
from app.services.payment_domain import (
    RESERVATION_STATUS_CANCELLED,
    RESERVATION_STATUS_COMPLETED,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_IN_PROGRESS,
    RESERVATION_STATUS_EXPIRED,
    RESERVATION_STATUS_PENDING_PAYMENT,
    RESERVATION_STATUS_PENDING_REVIEW,
    RESERVATION_STATUS_RETURNED_PENDING_CLOSURE,
)


RESERVATION_STATUS_LABELS = {
    RESERVATION_STATUS_PENDING_REVIEW: "Pendiente de revisión",
    RESERVATION_STATUS_PENDING_PAYMENT: "Pendiente de pago",
    RESERVATION_STATUS_CONFIRMED: "Confirmada",
    RESERVATION_STATUS_CANCELLED: "Cancelada",
    RESERVATION_STATUS_EXPIRED: "Caducada",
    RESERVATION_STATUS_IN_PROGRESS: "En alquiler",
    RESERVATION_STATUS_RETURNED_PENDING_CLOSURE: "Devuelta pendiente de cierre",
    RESERVATION_STATUS_COMPLETED: "Finalizada",
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
    if reservation.status != RESERVATION_STATUS_PENDING_PAYMENT or reservation.payment_expires_at is None:
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
        or_(
            # A physically delivered tool remains unavailable until its actual
            # return, regardless of the original contractual end date.
            and_(
                Reservation.tool_id == tool_id,
                Reservation.status == RESERVATION_STATUS_IN_PROGRESS,
            ),
            and_(
                Reservation.tool_id == tool_id,
                *inclusive_date_range_conditions(Reservation, start_date, end_date),
                Reservation.status == RESERVATION_STATUS_CONFIRMED,
            ),
            and_(
                Reservation.tool_id == tool_id,
                *inclusive_date_range_conditions(Reservation, start_date, end_date),
                Reservation.status == RESERVATION_STATUS_PENDING_REVIEW,
            ),
            and_(
                Reservation.tool_id == tool_id,
                *inclusive_date_range_conditions(Reservation, start_date, end_date),
                Reservation.status == RESERVATION_STATUS_PENDING_PAYMENT,
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


def has_active_rental(session: Session, tool_id: int) -> bool:
    """Return whether a tool is physically out with no recorded return."""
    return session.execute(
        select(Reservation.id)
        .where(
            Reservation.tool_id == tool_id,
            Reservation.status == RESERVATION_STATUS_IN_PROGRESS,
        )
        .limit(1)
    ).scalar_one_or_none() is not None


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


def get_tool_unavailable_ranges(
    session: Session,
    tool_id: int,
    start_date: date,
    end_date: date,
    now: datetime | None = None,
) -> list[tuple[date, date]]:
    """Return merged, clipped public unavailable ranges without operational details."""
    # Open-ended active rentals are reported separately. They cannot be truthfully
    # represented by a fabricated end date in the public calendar response.
    reservation_ranges = session.execute(
        select(Reservation.start_date, Reservation.end_date).where(
            Reservation.tool_id == tool_id,
            *inclusive_date_range_conditions(Reservation, start_date, end_date),
            or_(
                Reservation.status == RESERVATION_STATUS_CONFIRMED,
                Reservation.status == RESERVATION_STATUS_PENDING_REVIEW,
                and_(
                    Reservation.status == RESERVATION_STATUS_PENDING_PAYMENT,
                    Reservation.payment_expires_at > (utc_now() if now is None else now),
                ),
            ),
        )
    ).all()
    block_ranges = session.execute(
        select(ToolBlock.start_date, ToolBlock.end_date).where(
            ToolBlock.tool_id == tool_id,
            *inclusive_date_range_conditions(ToolBlock, start_date, end_date),
        )
    ).all()

    clipped_ranges = sorted(
        (
            max(range_start, start_date),
            min(range_end, end_date),
        )
        for range_start, range_end in [*reservation_ranges, *block_ranges]
    )

    merged_ranges: list[tuple[date, date]] = []
    for range_start, range_end in clipped_ranges:
        if not merged_ranges or range_start > merged_ranges[-1][1] + timedelta(days=1):
            merged_ranges.append((range_start, range_end))
            continue

        merged_ranges[-1] = (merged_ranges[-1][0], max(merged_ranges[-1][1], range_end))

    return merged_ranges


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
