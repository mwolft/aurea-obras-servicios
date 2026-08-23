from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Reservation, Tool
from app.services.availability import has_blocking_reservation, has_tool_block, utc_now
from app.services.quotes import QuoteCalculationError, ReservationQuote, calculate_quote


class ReservationToolNotFoundError(Exception):
    """Raised when a reservation is requested for a non-public tool."""


class ReservationUnavailableError(Exception):
    """Raised when a tool cannot be reserved for the requested date range."""


class ReservationFulfillmentUnavailableError(Exception):
    """Raised when the requested pickup or delivery method is not configured."""


class ReservationReviewError(Exception):
    """Raised when a delivery reservation cannot be moved to payment."""


class ReservationCancellationError(Exception):
    """Raised when a reservation cannot transition to cancelled."""


def apply_quote(reservation: Reservation, quote: ReservationQuote) -> None:
    """Copy the authoritative quote to immutable-in-practice reservation snapshots."""
    reservation.billable_km = quote.billable_km
    reservation.daily_price_snapshot = quote.daily_price_snapshot
    reservation.delivery_price_per_km_snapshot = quote.delivery_price_per_km_snapshot
    reservation.charged_days = quote.charged_days
    reservation.rental_amount = quote.rental_amount
    reservation.delivery_amount = quote.delivery_amount
    reservation.total_amount = quote.total_amount


def create_reservation(
    tool_id: int,
    start_date: date,
    end_date: date,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    terms_accepted: bool,
    privacy_accepted: bool,
    fulfillment_method: str,
    delivery_address: str | None = None,
    session: Session | None = None,
    now: datetime | None = None,
    user_id: int | None = None,
) -> Reservation:
    """Create a pickup checkout or delivery review after serializing writes for its tool."""
    reservation_session = db.session if session is None else session

    with reservation_session.begin():
        tool = (
            reservation_session.execute(
                select(Tool)
                .where(Tool.id == tool_id, Tool.is_published.is_(True))
                .with_for_update()
            )
            .scalar_one_or_none()
        )

        if tool is None:
            raise ReservationToolNotFoundError

        if not tool.is_available:
            raise ReservationUnavailableError

        if fulfillment_method == "pickup" and not tool.pickup_available:
            raise ReservationFulfillmentUnavailableError

        if fulfillment_method == "delivery" and (
            not tool.delivery_available or tool.delivery_price_per_km is None
        ):
            raise ReservationFulfillmentUnavailableError

        current_time = utc_now() if now is None else now

        if has_blocking_reservation(
            reservation_session,
            tool.id,
            start_date,
            end_date,
            current_time,
        ) or has_tool_block(reservation_session, tool.id, start_date, end_date):
            raise ReservationUnavailableError

        reservation = Reservation(
            tool_id=tool.id,
            start_date=start_date,
            end_date=end_date,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            terms_accepted=terms_accepted,
            privacy_accepted=privacy_accepted,
            fulfillment_method=fulfillment_method,
            user_id=user_id,
        )

        if fulfillment_method == "pickup":
            quote = calculate_quote(tool, start_date, end_date, fulfillment_method)
            apply_quote(reservation, quote)
            reservation.status = "pending_payment"
            reservation.payment_expires_at = current_time + timedelta(minutes=15)
        elif fulfillment_method == "delivery":
            reservation.status = "pending_review"
            reservation.delivery_address = delivery_address
            reservation.payment_expires_at = None
        else:
            raise ReservationFulfillmentUnavailableError

        reservation_session.add(reservation)
        reservation_session.flush()

    return reservation


def review_delivery_reservation(
    reservation_id: int,
    billable_km: Decimal,
    session: Session | None = None,
    now: datetime | None = None,
) -> Reservation:
    """Freeze a reviewed delivery quote and start its payment window.

    This domain operation is intentionally not exposed through a public route or
    a generic Flask-Admin form.
    """
    reservation_session = db.session if session is None else session

    with reservation_session.begin():
        reservation = (
            reservation_session.execute(
                select(Reservation).where(Reservation.id == reservation_id).with_for_update()
            )
            .scalar_one_or_none()
        )

        if (
            reservation is None
            or reservation.status != "pending_review"
            or reservation.fulfillment_method != "delivery"
        ):
            raise ReservationReviewError

        tool = (
            reservation_session.execute(
                select(Tool).where(Tool.id == reservation.tool_id).with_for_update()
            )
            .scalar_one()
        )

        if not tool.is_available or not tool.delivery_available:
            raise ReservationReviewError

        try:
            quote = calculate_quote(
                tool,
                reservation.start_date,
                reservation.end_date,
                "delivery",
                billable_km,
            )
        except QuoteCalculationError as error:
            raise ReservationReviewError from error

        apply_quote(reservation, quote)
        reservation.status = "pending_payment"
        current_time = utc_now() if now is None else now
        reservation.payment_expires_at = current_time + timedelta(minutes=15)
        reservation_session.flush()

    return reservation


def cancel_reservation(
    reservation_id: int,
    session: Session | None = None,
) -> Reservation:
    """Cancel an operational reservation through a serialized state transition.

    Locking the reservation makes concurrent cancellation attempts deterministic.
    Reservation creation still serializes on the tool row, so a concurrent create
    either sees the reservation before it is cancelled and conflicts, or sees its
    committed cancelled state and can proceed safely.
    """
    reservation_session = db.session if session is None else session

    with reservation_session.begin():
        reservation = (
            reservation_session.execute(
                select(Reservation).where(Reservation.id == reservation_id).with_for_update()
            )
            .scalar_one_or_none()
        )

        if reservation is None or reservation.status not in {
            "pending_review",
            "pending_payment",
            "confirmed",
        }:
            raise ReservationCancellationError

        reservation.status = "cancelled"
        reservation_session.flush()

    return reservation
