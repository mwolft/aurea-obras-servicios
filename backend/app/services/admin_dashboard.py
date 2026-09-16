"""Read-only operational summary queries for the Flask-Admin home page."""

from dataclasses import dataclass
from datetime import date, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.extensions import db
from app.models import EmailOutbox, Payment, Reservation, Tool
from app.services.availability import utc_now
from app.services.deposit_operations import (
    DepositOperationalState,
    evaluate_deposit_operational_state,
)
from app.services.payment_domain import (
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_PAID,
)
from app.services.email.rental import EVENT_DEPOSIT_AUTOMATION_FAILED
from app.services.rental_lifecycle import is_reservation_overdue


UPCOMING_ACTIVITY_DAYS = 30


@dataclass(frozen=True)
class DashboardMetrics:
    pending_reservations: int
    upcoming_deliveries: int
    upcoming_returns: int
    available_tools: int
    published_tools: int
    active_rentals: int
    overdue_rentals: int
    returned_pending_closure: int


@dataclass(frozen=True)
class DashboardActivity:
    date: date
    operation: str
    reservation_id: int
    tool_name: str
    customer_name: str
    fulfillment_method: str


@dataclass(frozen=True)
class DashboardDepositFollowUp:
    reservation_id: int
    tool_name: str
    customer_name: str
    start_date: date
    end_date: date
    deposit_amount: Decimal
    operational_state: DepositOperationalState


@dataclass(frozen=True)
class DashboardSummary:
    metrics: DashboardMetrics
    upcoming_activity: tuple[DashboardActivity, ...]
    pending_delivery_reviews: int
    deposit_attention: tuple[DashboardDepositFollowUp, ...]
    deposit_waiting_customer: tuple[DashboardDepositFollowUp, ...]


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
    upcoming_returns = _count_upcoming_returns(dashboard_session, current_date, horizon_date)
    available_tools, published_tools = _count_available_tools(dashboard_session)
    active_rentals, overdue_rentals = _get_active_rental_counts(dashboard_session, current_time)
    returned_pending_closure = dashboard_session.execute(
        select(func.count(Reservation.id)).where(
            Reservation.status == "returned_pending_closure"
        )
    ).scalar_one()

    deposit_attention, deposit_waiting_customer = _get_deposit_follow_up(
        dashboard_session, current_time
    )

    return DashboardSummary(
        metrics=DashboardMetrics(
            pending_reservations=pending_reservations,
            upcoming_deliveries=upcoming_deliveries,
            upcoming_returns=upcoming_returns,
            available_tools=available_tools,
            published_tools=published_tools,
            active_rentals=active_rentals,
            overdue_rentals=overdue_rentals,
            returned_pending_closure=returned_pending_closure,
        ),
        upcoming_activity=tuple(
            _get_upcoming_activity(dashboard_session, current_date, horizon_date, activity_limit)
        ),
        pending_delivery_reviews=pending_delivery_reviews,
        deposit_attention=tuple(deposit_attention),
        deposit_waiting_customer=tuple(deposit_waiting_customer),
    )


def _get_deposit_follow_up(
    session: Session,
    current_time,
) -> tuple[list[DashboardDepositFollowUp], list[DashboardDepositFollowUp]]:
    """Return derived deposit work queues without changing financial state."""
    reservations = list(
        session.execute(
            select(Reservation)
            .options(joinedload(Reservation.tool))
            .where(
                Reservation.status == "confirmed",
                Reservation.deposit_amount_snapshot.is_not(None),
                Reservation.deposit_amount_snapshot > 0,
            )
            .order_by(Reservation.start_date, Reservation.id)
        ).scalars()
    )
    if not reservations:
        return [], []

    reservation_ids = [reservation.id for reservation in reservations]
    payments = list(
        session.execute(
            select(Payment)
            .where(Payment.reservation_id.in_(reservation_ids))
            .order_by(Payment.reservation_id, Payment.id.desc())
        ).scalars()
    )
    latest_deposits: dict[int, Payment] = {}
    rental_paid: set[int] = set()
    for payment in payments:
        if payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE and payment.status == PAYMENT_STATUS_PAID:
            rental_paid.add(payment.reservation_id)
        if (
            payment.purpose == PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION
            and payment.reservation_id not in latest_deposits
        ):
            latest_deposits[payment.reservation_id] = payment

    payment_ids = [payment.id for payment in latest_deposits.values()]
    request_emails: dict[int, EmailOutbox] = {}
    if payment_ids:
        emails = list(
            session.execute(
                select(EmailOutbox).where(
                    EmailOutbox.idempotency_key.in_(
                        [f"deposit:{payment_id}:authorization_requested" for payment_id in payment_ids]
                    )
                )
            ).scalars()
        )
        for email in emails:
            try:
                payment_id = int(email.idempotency_key.split(":")[1])
            except (IndexError, ValueError):  # pragma: no cover - defensive history handling.
                continue
            request_emails[payment_id] = email

    latest_automation_alerts: dict[int, EmailOutbox] = {}
    alerts = list(
        session.execute(
            select(EmailOutbox)
            .where(
                EmailOutbox.reservation_id.in_(reservation_ids),
                EmailOutbox.event_type == EVENT_DEPOSIT_AUTOMATION_FAILED,
            )
            .order_by(EmailOutbox.reservation_id, EmailOutbox.created_at.desc())
        ).scalars()
    )
    for alert in alerts:
        latest_automation_alerts.setdefault(alert.reservation_id, alert)

    attention: list[DashboardDepositFollowUp] = []
    waiting: list[DashboardDepositFollowUp] = []
    for reservation in reservations:
        payment = latest_deposits.get(reservation.id)
        alert = latest_automation_alerts.get(reservation.id)
        payment_created_at = payment.created_at if payment is not None else None
        if payment_created_at is not None and payment_created_at.tzinfo is None:
            payment_created_at = payment_created_at.replace(tzinfo=timezone.utc)
        alert_created_at = alert.created_at if alert is not None else None
        if alert_created_at is not None and alert_created_at.tzinfo is None:
            alert_created_at = alert_created_at.replace(tzinfo=timezone.utc)
        state = evaluate_deposit_operational_state(
            reservation,
            payment,
            request_emails.get(payment.id) if payment is not None else None,
            rental_paid=reservation.id in rental_paid,
            automation_failed=(
                alert_created_at is not None
                and (payment_created_at is None or alert_created_at >= payment_created_at)
            ),
            now=current_time,
        )
        item = DashboardDepositFollowUp(
            reservation_id=reservation.id,
            tool_name=reservation.tool.name,
            customer_name=reservation.customer_name or "Cliente",
            start_date=reservation.start_date,
            end_date=reservation.end_date,
            deposit_amount=Decimal(reservation.deposit_amount_snapshot),
            operational_state=state,
        )
        if state.requires_attention:
            attention.append(item)
        elif state.awaiting_customer:
            waiting.append(item)
    return attention, waiting


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


def _count_upcoming_returns(session: Session, start_date: date, end_date: date) -> int:
    return session.execute(
        select(func.count(Reservation.id)).where(
            Reservation.status.in_(("confirmed", "in_progress")),
            Reservation.end_date.between(start_date, end_date),
        )
    ).scalar_one()


def _get_active_rental_counts(session: Session, current_time) -> tuple[int, int]:
    active_rentals = session.execute(
        select(Reservation).where(Reservation.status == "in_progress")
    ).scalars().all()
    return len(active_rentals), sum(
        1 for reservation in active_rentals if is_reservation_overdue(reservation, current_time)
    )


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
            Reservation.status.in_(("confirmed", "in_progress")),
            or_(
                Reservation.start_date.between(start_date, end_date),
                Reservation.end_date.between(start_date, end_date),
            ),
        )
    ).scalars().all()

    activity: list[DashboardActivity] = []
    for reservation in reservations:
        if (
            reservation.status == "confirmed"
            and start_date <= reservation.start_date <= end_date
        ):
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
