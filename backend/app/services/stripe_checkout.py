"""Stripe Checkout integration for the rental payment domain.

The browser only receives a hosted Checkout URL.  Reservation confirmation is
deliberately kept out of this module's initiation flow and happens exclusively
when the signed Stripe webhook is processed.
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import stripe
from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Payment, Reservation, Tool
from app.services.availability import is_pending_payment_expired, utc_now
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_REQUIRES_REVIEW,
    PAYMENT_WINDOW,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_PENDING_PAYMENT,
)
from app.services.email.rental import queue_financial_alert, queue_reservation_confirmed


logger = logging.getLogger(__name__)

STRIPE_CURRENCY = "eur"
STRIPE_SUCCESS_EVENT_TYPES = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
}


class StripeConfigurationError(RuntimeError):
    """Raised when Stripe credentials have not been configured."""


class StripeCheckoutError(RuntimeError):
    """Raised when Stripe cannot create or retrieve Checkout."""


class ReservationPaymentNotFoundError(RuntimeError):
    """Raised when a reservation is not visible to the requested payment flow."""


class ReservationPaymentStateError(RuntimeError):
    """Raised when a reservation is not eligible for a new payment."""


class ReservationPaymentExpiredError(ReservationPaymentStateError):
    """Raised when the payment hold has elapsed."""


def _stripe_secret_key() -> str:
    secret_key = current_app.config.get("STRIPE_SECRET_KEY")
    if not secret_key:
        raise StripeConfigurationError("Stripe is not configured.")
    return secret_key


def _stripe_webhook_secret() -> str:
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise StripeConfigurationError("Stripe webhook verification is not configured.")
    return webhook_secret


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        from datetime import timezone

        return value.replace(tzinfo=timezone.utc)
    return value


def _amount_in_cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _object_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _metadata_value(value: Any, key: str) -> str | None:
    metadata = _object_value(value, "metadata", {})
    raw_value = _object_value(metadata, key)
    return raw_value if isinstance(raw_value, str) else None


def _checkout_urls(reservation: Reservation, session_deadline: datetime) -> dict[str, str | int]:
    frontend_origin = current_app.config["FRONTEND_ORIGIN"].rstrip("/")
    base_url = f"{frontend_origin}/alquiler/{reservation.tool_id}"
    return {
        "success_url": f"{base_url}?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base_url}?payment=cancelled&session_id={{CHECKOUT_SESSION_ID}}",
        "expires_at": int(_as_utc(session_deadline).timestamp()),
    }


def _assert_reservation_can_start_payment(reservation: Reservation, now: datetime) -> None:
    if reservation.status != RESERVATION_STATUS_PENDING_PAYMENT:
        raise ReservationPaymentStateError("The reservation is not pending payment.")
    if is_pending_payment_expired(reservation, now):
        raise ReservationPaymentExpiredError("The payment window has expired.")
    if reservation.total_amount is None:
        raise ReservationPaymentStateError("The reservation does not have a final total.")


def _create_checkout_session(payment: Payment, reservation: Reservation, tool: Tool) -> Any:
    stripe.api_key = _stripe_secret_key()
    checkout_data = _checkout_urls(reservation, payment.expires_at)
    try:
        return stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=reservation.customer_email,
            client_reference_id=str(payment.id),
            metadata={
                "payment_id": str(payment.id),
                "reservation_id": str(reservation.id),
            },
            payment_intent_data={
                "metadata": {
                    "payment_id": str(payment.id),
                    "reservation_id": str(reservation.id),
                }
            },
            line_items=[
                {
                    "price_data": {
                        "currency": payment.currency,
                        "unit_amount": _amount_in_cents(Decimal(payment.amount)),
                        "product_data": {"name": f"Alquiler: {tool.name}"},
                    },
                    "quantity": 1,
                }
            ],
            **checkout_data,
            idempotency_key=payment.idempotency_key,
        )
    except stripe.StripeError as error:
        raise StripeCheckoutError("Stripe could not create Checkout.") from error


def _retrieve_checkout_session(external_payment_id: str) -> Any:
    stripe.api_key = _stripe_secret_key()
    try:
        return stripe.checkout.Session.retrieve(external_payment_id)
    except stripe.StripeError as error:
        raise StripeCheckoutError("Stripe Checkout could not be retrieved.") from error


def _checkout_url(session: Any) -> str:
    checkout_url = _object_value(session, "url")
    if not isinstance(checkout_url, str) or not checkout_url.startswith("https://"):
        raise StripeCheckoutError("Stripe Checkout did not return a valid URL.")
    return checkout_url


def start_or_recover_stripe_checkout(
    reservation_id: int,
    user_id: int | None,
    session: Session | None = None,
    now: datetime | None = None,
) -> str:
    """Create at most one active Stripe Checkout session for a reservation.

    A first successful checkout start refreshes the reservation deadline to the
    30-minute Checkout deadline.  Stripe requires Checkout sessions to have at
    least a 30-minute lifetime, so setting both persisted deadlines together is
    what keeps the provider and availability windows identical.
    """
    payment_session = db.session if session is None else session
    current_time = utc_now() if now is None else now

    with payment_session.begin():
        reservation = (
            payment_session.execute(
                select(Reservation).where(Reservation.id == reservation_id).with_for_update()
            )
            .scalar_one_or_none()
        )
        if reservation is None or (
            reservation.user_id is not None and reservation.user_id != user_id
        ):
            raise ReservationPaymentNotFoundError

        _assert_reservation_can_start_payment(reservation, current_time)
        other_pending_payment = payment_session.execute(
            select(Payment.id)
            .where(
                Payment.reservation_id == reservation.id,
                Payment.provider != PAYMENT_PROVIDER_STRIPE,
                Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
                Payment.status == PAYMENT_STATUS_PENDING,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if other_pending_payment is not None:
            raise ReservationPaymentStateError("Another payment method is already active.")
        tool = payment_session.execute(
            select(Tool).where(Tool.id == reservation.tool_id)
        ).scalar_one()
        payment = payment_session.execute(
            select(Payment)
            .where(
                Payment.reservation_id == reservation.id,
                Payment.provider == PAYMENT_PROVIDER_STRIPE,
                Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
                Payment.status == PAYMENT_STATUS_PENDING,
            )
            .with_for_update()
        ).scalar_one_or_none()

        if payment is None:
            # The deadline begins when a hosted checkout is actually issued,
            # keeping Stripe's minimum lifetime aligned with availability.
            checkout_deadline = current_time + PAYMENT_WINDOW
            reservation.payment_expires_at = checkout_deadline
            payment = Payment(
                reservation_id=reservation.id,
                provider=PAYMENT_PROVIDER_STRIPE,
                purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
                status=PAYMENT_STATUS_PENDING,
                amount=Decimal(reservation.total_amount),
                currency=STRIPE_CURRENCY,
                idempotency_key=uuid.uuid4().hex,
                expires_at=checkout_deadline,
            )
            payment_session.add(payment)
            payment_session.flush()

        external_payment_id = payment.external_payment_id
        if external_payment_id:
            return _checkout_url(_retrieve_checkout_session(external_payment_id))

        # Keep the idempotency key stable if the provider call is retried after
        # a transport failure. Stripe then returns the same Checkout session
        # instead of creating a duplicate. Holding the reservation lock during
        # this short provider call also makes concurrent starts deterministic.
        checkout_session = _create_checkout_session(payment, reservation, tool)
        external_payment_id = _object_value(checkout_session, "id")
        if not isinstance(external_payment_id, str) or not external_payment_id:
            raise StripeCheckoutError("Stripe Checkout did not return an identifier.")
        payment.external_payment_id = external_payment_id
        return _checkout_url(checkout_session)


def get_stripe_checkout_status(external_payment_id: str) -> dict[str, object] | None:
    """Return a deliberately minimal browser-safe status for a Checkout return."""
    payment = db.session.execute(
        select(Payment, Reservation)
        .join(Reservation, Reservation.id == Payment.reservation_id)
        .where(
            Payment.provider == PAYMENT_PROVIDER_STRIPE,
            Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
            Payment.external_payment_id == external_payment_id,
        )
    ).one_or_none()
    if payment is None:
        return None

    payment_record, reservation = payment
    return {
        "payment_status": payment_record.status,
        "reservation_status": reservation.status,
        "payment_expired": is_pending_payment_expired(reservation),
    }


def construct_stripe_event(payload: bytes, signature: str | None) -> Any:
    if not signature:
        raise ValueError("Missing Stripe signature.")
    stripe.api_key = _stripe_secret_key()
    return stripe.Webhook.construct_event(payload, signature, _stripe_webhook_secret())


def _record_outbox_id(outbox_ids: list[int] | None, email) -> None:
    if outbox_ids is not None and email is not None:
        outbox_ids.append(email.id)


def _mark_payment_for_review(
    session: Session, payment: Payment, event_id: str, outbox_ids: list[int] | None
) -> None:
    payment.status = PAYMENT_STATUS_REQUIRES_REVIEW
    payment.provider_event_id = event_id
    _record_outbox_id(outbox_ids, queue_financial_alert(session, payment, "financial_review_required"))


def process_stripe_event(
    event: Any,
    session: Session | None = None,
    now: datetime | None = None,
    outbox_ids: list[int] | None = None,
) -> str:
    """Process a verified Stripe event without ever trusting the browser.

    Returns a compact processing outcome for the HTTP route.  Late or
    inconsistent successful payments are persisted as ``requires_review`` and
    deliberately do not confirm the reservation.
    """
    event_type = _object_value(event, "type")
    if event_type not in STRIPE_SUCCESS_EVENT_TYPES:
        return "ignored"

    event_id = _object_value(event, "id")
    session_object = _object_value(_object_value(event, "data", {}), "object", {})
    external_payment_id = _object_value(session_object, "id")
    payment_id = _metadata_value(session_object, "payment_id") or _object_value(
        session_object, "client_reference_id"
    )
    if not isinstance(event_id, str) or not isinstance(external_payment_id, str) or not isinstance(payment_id, str):
        logger.error("Stripe event is missing the expected payment references.")
        return "requires_review"
    try:
        internal_payment_id = int(payment_id)
    except ValueError:
        logger.error("Stripe event contains an invalid internal payment reference.")
        return "requires_review"
    if _object_value(session_object, "payment_status") != "paid":
        return "ignored"

    payment_session = db.session if session is None else session
    current_time = utc_now() if now is None else now
    with payment_session.begin():
        payment = (
            payment_session.execute(
                select(Payment)
                .where(
                    Payment.id == internal_payment_id,
                    Payment.provider == PAYMENT_PROVIDER_STRIPE,
                    Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
                )
                .with_for_update()
            )
            .scalar_one_or_none()
        )
        if payment is None or payment.external_payment_id != external_payment_id:
            logger.error("Stripe event does not match a known Checkout payment.")
            return "requires_review"

        if payment.provider_event_id == event_id or payment.status == PAYMENT_STATUS_PAID:
            return "duplicate"

        reservation = (
            payment_session.execute(
                select(Reservation).where(Reservation.id == payment.reservation_id).with_for_update()
            )
            .scalar_one()
        )
        amount_total = _object_value(session_object, "amount_total")
        currency = _object_value(session_object, "currency")
        expected_amount = _amount_in_cents(Decimal(payment.amount))
        if (
            amount_total != expected_amount
            or not isinstance(currency, str)
            or currency.lower() != payment.currency.lower()
            or reservation.total_amount is None
            or Decimal(reservation.total_amount) != Decimal(payment.amount)
        ):
            logger.error("Stripe payment amount or currency does not match its reservation snapshot.")
            _mark_payment_for_review(payment_session, payment, event_id, outbox_ids)
            return "requires_review"

        if (
            reservation.status != RESERVATION_STATUS_PENDING_PAYMENT
            or is_pending_payment_expired(reservation, current_time)
        ):
            logger.warning("Stripe payment arrived after its reservation payment window.")
            _mark_payment_for_review(payment_session, payment, event_id, outbox_ids)
            return "requires_review"

        payment.status = PAYMENT_STATUS_PAID
        payment.provider_event_id = event_id
        payment.paid_at = current_time
        reservation.status = RESERVATION_STATUS_CONFIRMED
        _record_outbox_id(outbox_ids, queue_reservation_confirmed(payment_session, reservation))
        return "confirmed"
