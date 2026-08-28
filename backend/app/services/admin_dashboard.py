"""Read-only operational summary queries for the Flask-Admin home page."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.extensions import db
from app.models import Reservation, Tool
from app.services.availability import utc_now


UPCOMING_ACTIVITY_DAYS = 30


@dataclass(frozen=True)
class DashboardMetrics:
    pending_reservations: int
    upcoming_deliveries: int
    upcoming_returns: int
    available_tools: int
    published_tools: int


@dataclass(frozen=True)
class DashboardActivity:
    date: date
    operation: str
    reservation_id: int
    tool_name: str
    customer_name: str
    fulfillment_method: str


@dataclass(frozen=True)
class DashboardSummary:
    metrics: DashboardMetrics
    upcoming_activity: tuple[DashboardActivity, ...]
    pending_delivery_reviews: int


def get_dashboard_summary(
    session: Session | None = None,
    *,
    today: date | None = None,
    activity_limit: int = 5,
) -> DashboardSummary:
    """Return the small, read-only operational summary used by ``/admin/``.

    Only confirmed reservations are logistics-ready, so they are the sole source
    of upcoming deliveries and returns. Pending delivery reviews are the only
    current reservation state with a defined administrative action.
    """
    dashboard_session = db.session if session is None else session
    current_date = date.today() if today is None else today
    horizon_date = current_date + timedelta(days=UPCOMING_ACTIVITY_DAYS)
    current_time = utc_now()

    pending_reservations = _count_pending_reservations(dashboard_session, current_time)
    pending_delivery_reviews = _count_pending_delivery_reviews(dashboard_session)
    upcoming_deliveries = _count_upcoming_operations(
        dashboard_session, Reservation.start_date, current_date, horizon_date
    )
    upcoming_returns = _count_upcoming_operations(
        dashboard_session, Reservation.end_date, current_date, horizon_date
    )
    available_tools, published_tools = _count_available_tools(dashboard_session)

    return DashboardSummary(
        metrics=DashboardMetrics(
            pending_reservations=pending_reservations,
            upcoming_deliveries=upcoming_deliveries,
            upcoming_returns=upcoming_returns,
            available_tools=available_tools,
            published_tools=published_tools,
        ),
        upcoming_activity=tuple(
            _get_upcoming_activity(dashboard_session, current_date, horizon_date, activity_limit)
        ),
        pending_delivery_reviews=pending_delivery_reviews,
    )


def _count_pending_reservations(session: Session, current_time) -> int:
    """Count live checkout/review work without treating expired checkout as live."""
    return session.execute(
        select(func.count(Reservation.id)).where(
            or_(
                Reservation.status == "pending_review",
                and_(
                    Reservation.status == "pending_payment",
                    Reservation.payment_expires_at > current_time,
                ),
            )
        )
    ).scalar_one()


def _count_pending_delivery_reviews(session: Session) -> int:
    return session.execute(
        select(func.count(Reservation.id)).where(
            Reservation.status == "pending_review",
            Reservation.fulfillment_method == "delivery",
        )
    ).scalar_one()


def _count_upcoming_operations(session: Session, operation_date, start_date: date, end_date: date) -> int:
    return session.execute(
        select(func.count(Reservation.id)).where(
            Reservation.status == "confirmed",
            operation_date.between(start_date, end_date),
        )
    ).scalar_one()


def _count_available_tools(session: Session) -> tuple[int, int]:
    published_tools = session.execute(
        select(func.count(Tool.id)).where(Tool.is_published.is_(True))
    ).scalar_one()
    available_tools = session.execute(
        select(func.count(Tool.id)).where(
            Tool.is_published.is_(True), Tool.is_available.is_(True)
        )
    ).scalar_one()
    return available_tools, published_tools


def _get_upcoming_activity(
    session: Session,
    start_date: date,
    end_date: date,
    limit: int,
) -> list[DashboardActivity]:
    reservations = session.execute(
        select(Reservation)
        .options(joinedload(Reservation.tool))
        .where(
            Reservation.status == "confirmed",
            or_(
                Reservation.start_date.between(start_date, end_date),
                Reservation.end_date.between(start_date, end_date),
            ),
        )
    ).scalars().all()

    activity: list[DashboardActivity] = []
    for reservation in reservations:
        if start_date <= reservation.start_date <= end_date:
            activity.append(
                DashboardActivity(
                    date=reservation.start_date,
                    operation="Entrega",
                    reservation_id=reservation.id,
                    tool_name=reservation.tool.name,
                    customer_name=reservation.customer_name,
                    fulfillment_method=reservation.fulfillment_method,
                )
            )
        if start_date <= reservation.end_date <= end_date:
            activity.append(
                DashboardActivity(
                    date=reservation.end_date,
                    operation="Devolución",
                    reservation_id=reservation.id,
                    tool_name=reservation.tool.name,
                    customer_name=reservation.customer_name,
                    fulfillment_method=reservation.fulfillment_method,
                )
            )

    return sorted(
        activity,
        key=lambda item: (item.date, 0 if item.operation == "Entrega" else 1, item.reservation_id),
    )[:limit]
