"""Shared payment-domain constants and small state helpers.

Provider-specific code must use these values instead of introducing payment
state strings in routes or integrations.  The reservation state remains the
source of truth for availability; payment records capture the provider-facing
lifecycle separately.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any


PAYMENT_WINDOW_MINUTES = 30
PAYMENT_WINDOW = timedelta(minutes=PAYMENT_WINDOW_MINUTES)

RESERVATION_STATUS_PENDING_REVIEW = "pending_review"
RESERVATION_STATUS_PENDING_PAYMENT = "pending_payment"
RESERVATION_STATUS_CONFIRMED = "confirmed"
RESERVATION_STATUS_IN_PROGRESS = "in_progress"
RESERVATION_STATUS_RETURNED_PENDING_CLOSURE = "returned_pending_closure"
RESERVATION_STATUS_COMPLETED = "completed"
RESERVATION_STATUS_CANCELLED = "cancelled"
RESERVATION_STATUS_EXPIRED = "expired"

PAYMENT_PROVIDER_STRIPE = "stripe"
PAYMENT_PROVIDER_PAYPAL = "paypal"

PAYMENT_PURPOSE_RENTAL_CHARGE = "rental_charge"
PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION = "deposit_authorization"

PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_PROCESSING = "processing"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_EXPIRED = "expired"
PAYMENT_STATUS_REQUIRES_REVIEW = "requires_review"
PAYMENT_STATUS_SUPERSEDED = "superseded"
PAYMENT_STATUS_PENDING_AUTHORIZATION = "pending_authorization"
PAYMENT_STATUS_AUTHORIZED = "authorized"
PAYMENT_STATUS_RELEASED = "released"
PAYMENT_STATUS_CAPTURED_PARTIALLY = "captured_partially"
PAYMENT_STATUS_CAPTURED = "captured"
PAYMENT_STATUS_AUTHORIZATION_FAILED = "authorization_failed"
PAYMENT_STATUS_AUTHORIZATION_EXPIRED = "authorization_expired"


class PaymentAttemptConflictError(RuntimeError):
    """A rental payment has reached a state that must be reviewed first."""


def prepare_rental_payment_attempt(session: Any, reservation_id: int, provider: str):
    """Return the reusable pending attempt for ``provider`` when it is safe.

    A hosted checkout/order is only an attempt until its provider confirms a
    completed payment.  Selecting a different provider therefore supersedes
    the prior pending attempt in AUREA's domain.  It deliberately does *not*
    supersede a capture already in progress or an attempt that requires manual
    review: allowing a second checkout in either case could hide a double
    charge.
    """
    # Importing at call time avoids the model -> payment_domain import cycle.
    from sqlalchemy import select

    from app.models import Payment

    attempts = list(
        session.execute(
            select(Payment)
            .where(
                Payment.reservation_id == reservation_id,
                Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
                Payment.status.in_(
                    (
                        PAYMENT_STATUS_PENDING,
                        PAYMENT_STATUS_PROCESSING,
                        PAYMENT_STATUS_REQUIRES_REVIEW,
                        PAYMENT_STATUS_PAID,
                    )
                ),
            )
            .order_by(Payment.id.desc())
            .with_for_update()
        ).scalars()
    )

    if any(
        attempt.status
        in {
            PAYMENT_STATUS_PROCESSING,
            PAYMENT_STATUS_REQUIRES_REVIEW,
            PAYMENT_STATUS_PAID,
        }
        for attempt in attempts
    ):
        raise PaymentAttemptConflictError(
            "A payment is being processed or requires review."
        )

    reusable_attempt = None
    for attempt in attempts:
        if attempt.provider == provider and reusable_attempt is None:
            reusable_attempt = attempt
        elif attempt.status == PAYMENT_STATUS_PENDING:
            attempt.status = PAYMENT_STATUS_SUPERSEDED

    return reusable_attempt


def payment_window_expires_at(now: datetime) -> datetime:
    """Return the common availability and Stripe Checkout deadline."""
    return now + PAYMENT_WINDOW


def serialize_payment_return_reservation(reservation: Any) -> dict[str, object]:
    """Return only the reservation information needed after a hosted checkout.

    This payload deliberately contains no provider references, internal notes,
    or customer contact details. The payment-status endpoints remain the source
    of truth for the return screen; a URL parameter alone never confirms a
    reservation.
    """

    def amount(value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None

    return {
        "id": reservation.id,
        "tool": {"id": reservation.tool.id, "name": reservation.tool.name},
        "start_date": reservation.start_date.isoformat(),
        "end_date": reservation.end_date.isoformat(),
        "status": reservation.status,
        "fulfillment_method": reservation.fulfillment_method,
        "delivery_address": (
            reservation.delivery_address
            if reservation.fulfillment_method == "delivery"
            else None
        ),
        "total_amount": amount(reservation.total_amount),
        "deposit_amount": amount(reservation.deposit_amount_snapshot),
    }
