"""Stripe-only security-deposit authorizations for confirmed rentals.

This module intentionally does not change reservation confirmation or rental
payment state. It manages a distinct Payment purpose with Stripe manual capture.
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import stripe
from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Payment, PaymentEvent, Reservation, Tool
from app.services.availability import utc_now
from app.services.payment_domain import (
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
    PAYMENT_STATUS_AUTHORIZATION_FAILED,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CAPTURED_PARTIALLY,
    PAYMENT_STATUS_PENDING_AUTHORIZATION,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_RELEASED,
    PAYMENT_STATUS_REQUIRES_REVIEW,
    PAYMENT_WINDOW,
    RESERVATION_STATUS_CANCELLED,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_RETURNED_PENDING_CLOSURE,
)
from app.services.stripe_checkout import (
    ReservationPaymentNotFoundError,
    ReservationPaymentStateError,
    StripeCheckoutError,
    StripeConfigurationError,
)
from app.services.email.rental import (
    queue_deposit_authorized,
    queue_deposit_captured,
    queue_deposit_released,
    queue_financial_alert,
)


logger = logging.getLogger(__name__)
DEPOSIT_CURRENCY = "eur"
DEPOSIT_SUCCESS_EVENTS = {
    "payment_intent.amount_capturable_updated",
    "payment_intent.succeeded",
    "payment_intent.canceled",
    "payment_intent.payment_failed",
}


class DepositAuthorizationError(RuntimeError):
    """Raised when a deposit authorization cannot start or be managed."""


class DepositAuthorizationNotFoundError(DepositAuthorizationError):
    """Raised when a reservation has no matching deposit authorization."""


def _stripe_secret_key() -> str:
    secret_key = current_app.config.get("STRIPE_SECRET_KEY")
    if not secret_key:
        raise StripeConfigurationError("Stripe is not configured.")
    return secret_key


def _object_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _metadata_value(value: Any, key: str) -> str | None:
    metadata = _object_value(value, "metadata", {})
    raw_value = _object_value(metadata, key)
    return raw_value if isinstance(raw_value, str) else None


def _amount_in_cents(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _from_cents(amount: int | None) -> Decimal | None:
    return None if amount is None else (Decimal(amount) / Decimal(100)).quantize(Decimal("0.01"))


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _checkout_urls(reservation: Reservation, expires_at: datetime) -> dict[str, str | int]:
    origin = current_app.config["FRONTEND_ORIGIN"].rstrip("/")
    base = f"{origin}/alquiler/{reservation.tool_id}"
    return {
        "success_url": f"{base}?deposit=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}?deposit=cancelled&session_id={{CHECKOUT_SESSION_ID}}",
        "expires_at": int(_as_utc(expires_at).timestamp()),
    }


def _assert_eligible(session: Session, reservation: Reservation) -> Decimal:
    if reservation.status != RESERVATION_STATUS_CONFIRMED:
        raise ReservationPaymentStateError("La reserva debe estar confirmada antes de autorizar la fianza.")
    rental_payment_exists = session.execute(
        select(Payment.id).where(
            Payment.reservation_id == reservation.id,
            Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
            Payment.status == PAYMENT_STATUS_PAID,
        )
    ).scalar_one_or_none()
    if rental_payment_exists is None:
        raise ReservationPaymentStateError("El alquiler debe estar pagado antes de autorizar la fianza.")
    if reservation.deposit_amount_snapshot is None:
        raise ReservationPaymentStateError("Esta reserva antigua no tiene una fianza contractual congelada.")
    deposit = Decimal(reservation.deposit_amount_snapshot)
    if deposit <= 0:
        raise ReservationPaymentStateError("Esta reserva no requiere fianza.")
    return deposit


def _checkout_url(session: Any) -> str:
    checkout_url = _object_value(session, "url")
    if not isinstance(checkout_url, str) or not checkout_url.startswith("https://"):
        raise StripeCheckoutError("Stripe Checkout did not return a valid URL.")
    return checkout_url


def _create_checkout(payment: Payment, reservation: Reservation, tool: Tool) -> Any:
    stripe.api_key = _stripe_secret_key()
    try:
        return stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=reservation.customer_email,
            metadata={"payment_id": str(payment.id), "purpose": PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION},
            payment_intent_data={
                "capture_method": "manual",
                "metadata": {
                    "payment_id": str(payment.id),
                    "reservation_id": str(reservation.id),
                    "purpose": PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                },
            },
            line_items=[{
                "price_data": {
                    "currency": DEPOSIT_CURRENCY,
                    "unit_amount": _amount_in_cents(Decimal(payment.amount)),
                    "product_data": {"name": f"Fianza: {tool.name}"},
                },
                "quantity": 1,
            }],
            **_checkout_urls(reservation, payment.expires_at),
            idempotency_key=payment.idempotency_key,
        )
    except stripe.StripeError as error:
        raise StripeCheckoutError("Stripe could not create deposit Checkout.") from error


def _retrieve_checkout(checkout_id: str) -> Any:
    stripe.api_key = _stripe_secret_key()
    try:
        return stripe.checkout.Session.retrieve(checkout_id)
    except stripe.StripeError as error:
        raise StripeCheckoutError("Stripe deposit Checkout could not be retrieved.") from error


def _retrieve_payment_intent(payment_intent_id: str) -> Any:
    """Read Stripe's source of truth before replacing a stale authorization."""
    stripe.api_key = _stripe_secret_key()
    try:
        return stripe.PaymentIntent.retrieve(payment_intent_id)
    except stripe.StripeError as error:
        raise DepositAuthorizationError(
            "No se ha podido comprobar el estado de la autorización anterior en Stripe."
        ) from error


def _latest_deposit_payment(session: Session, reservation_id: int, *, lock: bool = False) -> Payment | None:
    statement = select(Payment).where(
        Payment.reservation_id == reservation_id,
        Payment.provider == PAYMENT_PROVIDER_STRIPE,
        Payment.purpose == PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    ).order_by(Payment.id.desc())
    if lock:
        statement = statement.with_for_update()
    return session.execute(statement).scalars().first()


def _deposit_payments(session: Session, reservation_id: int, *, lock: bool = False) -> list[Payment]:
    """Return the complete deposit history, newest first, for safety checks."""
    statement = select(Payment).where(
        Payment.reservation_id == reservation_id,
        Payment.provider == PAYMENT_PROVIDER_STRIPE,
        Payment.purpose == PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    ).order_by(Payment.id.desc())
    if lock:
        statement = statement.with_for_update()
    return list(session.execute(statement).scalars())


def _reconcile_expired_authorization(payment: Payment) -> bool:
    """Mark an elapsed card hold terminal only after Stripe confirms it.

    The old row deliberately remains intact for accounting and webhook audit
    history. A new authorization can be created only after this transition.
    """
    if not payment.external_payment_id:
        raise DepositAuthorizationError(
            "La autorización anterior requiere revisión antes de volver a intentarlo."
        )
    payment_intent = _retrieve_payment_intent(payment.external_payment_id)
    stripe_status = _object_value(payment_intent, "status")
    if stripe_status == "canceled":
        payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
        return True
    # A completed or otherwise unexpected PaymentIntent must never be treated
    # as an expired hold. Preserve it for a manual financial review instead.
    payment.status = PAYMENT_STATUS_REQUIRES_REVIEW
    return False


def start_or_recover_deposit_checkout(
    reservation_id: int,
    session: Session | None = None,
    now: datetime | None = None,
    user_id: int | None = None,
    is_admin: bool = True,
) -> str:
    """Create one card-only, manual-capture Checkout session for the deposit."""
    payment_session = db.session if session is None else session
    current_time = utc_now() if now is None else now
    deferred_error: ReservationPaymentStateError | None = None
    checkout_url: str | None = None
    with payment_session.begin():
        reservation = payment_session.execute(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        ).scalar_one_or_none()
        if reservation is None:
            raise ReservationPaymentNotFoundError
        if not is_admin and (reservation.user_id is None or reservation.user_id != user_id):
            raise ReservationPaymentNotFoundError
        deposit_amount = _assert_eligible(payment_session, reservation)
        payments = _deposit_payments(payment_session, reservation.id, lock=True)
        payment = payments[0] if payments else None
        # A reservation lock serializes normal starts. This second check also
        # protects against inconsistent historical data: never create another
        # hold while any older authorization can still charge a card.
        for previous_payment in payments[1:]:
            if previous_payment.status in {
                PAYMENT_STATUS_PENDING_AUTHORIZATION,
                PAYMENT_STATUS_AUTHORIZED,
                PAYMENT_STATUS_REQUIRES_REVIEW,
            }:
                raise ReservationPaymentStateError(
                    "Existe una autorización de fianza anterior que requiere revisión."
                )
        if payment is not None:
            if payment.status == PAYMENT_STATUS_AUTHORIZED:
                if not _capture_window_has_expired(payment, current_time):
                    raise ReservationPaymentStateError("La fianza ya está autorizada.")
                if not _reconcile_expired_authorization(payment):
                    # Commit the requires_review state before reporting the
                    # error; raising inside this transaction would roll it back.
                    deferred_error = ReservationPaymentStateError(
                        "Stripe indica que la autorización anterior se completó y requiere revisión."
                    )
            if deferred_error is None:
                if payment.status == PAYMENT_STATUS_PENDING_AUTHORIZATION and payment.provider_checkout_id:
                    checkout = _retrieve_checkout(payment.provider_checkout_id)
                    checkout_status = _object_value(checkout, "status")
                    if checkout_status == "open":
                        return _checkout_url(checkout)
                    if checkout_status == "complete":
                        raise ReservationPaymentStateError(
                            "La autorización está pendiente de confirmación por Stripe."
                        )
                    # A Checkout session has its own short-lived URL. Once Stripe
                    # expires it, it cannot be reused for a later handover.
                    payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
                elif payment.status == PAYMENT_STATUS_PENDING_AUTHORIZATION:
                    raise ReservationPaymentStateError(
                        "La autorización de fianza anterior requiere revisión antes de volver a intentarlo."
                    )
                if payment.status == PAYMENT_STATUS_REQUIRES_REVIEW:
                    raise ReservationPaymentStateError("La fianza requiere revisión antes de volver a intentarlo.")
                if payment.status in {PAYMENT_STATUS_CAPTURED, PAYMENT_STATUS_CAPTURED_PARTIALLY}:
                    raise ReservationPaymentStateError("La fianza ya fue capturada.")
                if payment.status == PAYMENT_STATUS_RELEASED:
                    raise ReservationPaymentStateError("La fianza ya fue liberada.")
                if payment.status not in {
                    PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
                    PAYMENT_STATUS_AUTHORIZATION_FAILED,
                }:
                    raise ReservationPaymentStateError(
                        "La autorización de fianza anterior no puede sustituirse todavía."
                    )
        if deferred_error is None:
            payment = Payment(
                reservation_id=reservation.id,
                provider=PAYMENT_PROVIDER_STRIPE,
                purpose=PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
                status=PAYMENT_STATUS_PENDING_AUTHORIZATION,
                amount=deposit_amount,
                currency=DEPOSIT_CURRENCY,
                idempotency_key=uuid.uuid4().hex,
                # This only controls the hosted Checkout session. The subsequent card
                # hold is governed solely by Stripe's capture_before value.
                expires_at=current_time + PAYMENT_WINDOW,
            )
            payment_session.add(payment)
            payment_session.flush()
            tool = payment_session.get(Tool, reservation.tool_id)
            checkout = _create_checkout(payment, reservation, tool)
            checkout_id = _object_value(checkout, "id")
            if not isinstance(checkout_id, str) or not checkout_id:
                raise StripeCheckoutError("Stripe did not return a deposit Checkout ID.")
            payment.provider_checkout_id = checkout_id
            checkout_url = _checkout_url(checkout)
    if deferred_error is not None:
        raise deferred_error
    if checkout_url is None:
        raise StripeCheckoutError("Stripe did not return a deposit Checkout URL.")
    return checkout_url


def _capture_before(payment_intent: Any) -> datetime | None:
    charge = _object_value(payment_intent, "latest_charge")
    details = _object_value(charge, "payment_method_details", {})
    card = _object_value(details, "card", {})
    timestamp = _object_value(card, "capture_before")
    if not isinstance(timestamp, int):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _charge_id(payment_intent: Any) -> str | None:
    charge = _object_value(payment_intent, "latest_charge")
    value = _object_value(charge, "id") if not isinstance(charge, str) else charge
    return value if isinstance(value, str) else None


def _event_seen(session: Session, provider_event_id: str) -> bool:
    return session.execute(
        select(PaymentEvent.id).where(
            PaymentEvent.provider == PAYMENT_PROVIDER_STRIPE,
            PaymentEvent.provider_event_id == provider_event_id,
        )
    ).scalar_one_or_none() is not None


def _record_event(session: Session, payment: Payment, event_id: str, event_type: str) -> None:
    session.add(PaymentEvent(
        payment_id=payment.id,
        provider=PAYMENT_PROVIDER_STRIPE,
        provider_event_id=event_id,
        event_type=event_type,
    ))
    payment.provider_event_id = event_id


def _record_outbox_id(outbox_ids: list[int] | None, email) -> None:
    if outbox_ids is not None and email is not None:
        outbox_ids.append(email.id)


def _stripe_id(value: Any) -> str | None:
    """Return an id from Stripe's string-or-object references."""
    if isinstance(value, str) and value:
        return value
    candidate = _object_value(value, "id")
    return candidate if isinstance(candidate, str) and candidate else None


def _mark_deposit_requires_review(
    session: Session, payment: Payment, outbox_ids: list[int] | None
) -> None:
    payment.status = PAYMENT_STATUS_REQUIRES_REVIEW
    _record_outbox_id(
        outbox_ids,
        queue_financial_alert(session, payment, "financial_review_required"),
    )


def _cancel_authorized_intent(
    session: Session,
    reservation: Reservation,
    payment: Payment,
    current_time: datetime,
    outbox_ids: list[int] | None,
    *,
    notify_customer: bool,
) -> bool:
    """Cancel a capturable hold and only mark it released after Stripe agrees."""
    if not payment.external_payment_id:
        return False
    try:
        stripe.api_key = _stripe_secret_key()
        intent = stripe.PaymentIntent.cancel(payment.external_payment_id)
    except (stripe.StripeError, StripeConfigurationError):
        return False
    if _object_value(intent, "status") != "canceled":
        return False
    payment.status = PAYMENT_STATUS_RELEASED
    payment.released_at = current_time
    if notify_customer:
        _record_outbox_id(
            outbox_ids,
            queue_deposit_released(session, reservation, payment),
        )
    return True


def _invalidate_pending_checkout(
    session: Session,
    reservation: Reservation,
    payment: Payment,
    current_time: datetime,
    outbox_ids: list[int] | None,
) -> bool:
    """Make a pending Checkout unusable, reconciling a raced completion safely."""
    if not payment.provider_checkout_id:
        return False
    try:
        checkout = _retrieve_checkout(payment.provider_checkout_id)
    except (StripeCheckoutError, StripeConfigurationError):
        return False

    checkout_status = _object_value(checkout, "status")
    if checkout_status == "open":
        try:
            stripe.api_key = _stripe_secret_key()
            expired_checkout = stripe.checkout.Session.expire(payment.provider_checkout_id)
        except (stripe.StripeError, StripeConfigurationError):
            return False
        if _object_value(expired_checkout, "status") != "expired":
            return False
        payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
        return True

    if checkout_status == "expired":
        payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
        return True

    if checkout_status != "complete":
        return False

    payment_intent_id = _stripe_id(_object_value(checkout, "payment_intent"))
    if payment_intent_id is None:
        payment_intent_id = payment.external_payment_id
    if payment_intent_id is None:
        return False
    payment.external_payment_id = payment_intent_id
    try:
        payment_intent = _retrieve_payment_intent(payment_intent_id)
    except (DepositAuthorizationError, StripeConfigurationError):
        return False
    intent_status = _object_value(payment_intent, "status")
    if intent_status == "canceled":
        payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
        return True
    if intent_status == "requires_capture":
        return _cancel_authorized_intent(
            session,
            reservation,
            payment,
            current_time,
            outbox_ids,
            notify_customer=True,
        )
    return False


def neutralize_deposit_for_reservation_cancellation(
    session: Session,
    reservation: Reservation,
    *,
    now: datetime | None = None,
    outbox_ids: list[int] | None = None,
) -> str | None:
    """Ensure a cancellable reservation has no usable card hold before cancellation.

    The caller owns the reservation transaction and lock.  A returned message
    means the caller must leave the reservation unchanged; the affected deposit
    has been recorded as ``requires_review`` for administrative follow-up.
    """
    current_time = utc_now() if now is None else now
    payments = _deposit_payments(session, reservation.id, lock=True)

    # Do not send Stripe cancellation requests if an already ambiguous payment
    # requires a person to reconcile it first.
    if any(payment.status == PAYMENT_STATUS_REQUIRES_REVIEW for payment in payments):
        return "No se puede cancelar mientras la fianza requiera revisión."
    if any(
        payment.status == PAYMENT_STATUS_PENDING_AUTHORIZATION
        and not payment.provider_checkout_id
        for payment in payments
    ):
        for payment in payments:
            if payment.status == PAYMENT_STATUS_PENDING_AUTHORIZATION:
                _mark_deposit_requires_review(session, payment, outbox_ids)
        return "No se puede cancelar porque la autorización de fianza requiere revisión."
    if any(
        payment.status == PAYMENT_STATUS_AUTHORIZED and not payment.external_payment_id
        for payment in payments
    ):
        for payment in payments:
            if payment.status == PAYMENT_STATUS_AUTHORIZED:
                _mark_deposit_requires_review(session, payment, outbox_ids)
        return "No se puede cancelar porque la autorización de fianza requiere revisión."

    for payment in payments:
        if payment.status == PAYMENT_STATUS_PENDING_AUTHORIZATION:
            if not _invalidate_pending_checkout(
                session, reservation, payment, current_time, outbox_ids
            ):
                _mark_deposit_requires_review(session, payment, outbox_ids)
                return "No se ha podido invalidar la autorización de fianza; requiere revisión."
            continue

        if payment.status != PAYMENT_STATUS_AUTHORIZED:
            continue

        if _capture_window_has_expired(payment, current_time):
            try:
                is_expired = _reconcile_expired_authorization(payment)
            except (DepositAuthorizationError, StripeConfigurationError):
                is_expired = False
            if is_expired:
                continue
            _mark_deposit_requires_review(session, payment, outbox_ids)
            return "No se ha podido confirmar el estado de la fianza; requiere revisión."

        if not _cancel_authorized_intent(
            session,
            reservation,
            payment,
            current_time,
            outbox_ids,
            notify_customer=True,
        ):
            _mark_deposit_requires_review(session, payment, outbox_ids)
            return "Stripe no ha confirmado la liberación de la fianza; requiere revisión."

    return None


def process_stripe_deposit_event(
    event: Any,
    session: Session | None = None,
    now: datetime | None = None,
    outbox_ids: list[int] | None = None,
) -> str:
    """Persist verified Stripe lifecycle events without changing reservation status."""
    event_type = _object_value(event, "type")
    if event_type not in DEPOSIT_SUCCESS_EVENTS:
        return "ignored"
    event_id = _object_value(event, "id")
    payment_intent = _object_value(_object_value(event, "data", {}), "object", {})
    payment_id = _metadata_value(payment_intent, "payment_id")
    purpose = _metadata_value(payment_intent, "purpose")
    intent_id = _object_value(payment_intent, "id")
    if not isinstance(event_id, str) or not isinstance(payment_id, str) or purpose != PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION or not isinstance(intent_id, str):
        return "ignored"
    try:
        internal_payment_id = int(payment_id)
    except ValueError:
        return "requires_review"
    payment_session = db.session if session is None else session
    current_time = utc_now() if now is None else now
    with payment_session.begin():
        if _event_seen(payment_session, event_id):
            return "duplicate"
        payment = payment_session.execute(
            select(Payment).where(
                Payment.id == internal_payment_id,
                Payment.provider == PAYMENT_PROVIDER_STRIPE,
                Payment.purpose == PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
            ).with_for_update()
        ).scalar_one_or_none()
        if payment is None:
            return "requires_review"
        reservation = payment_session.execute(
            select(Reservation).where(Reservation.id == payment.reservation_id).with_for_update()
        ).scalar_one()
        if reservation.deposit_amount_snapshot is None or Decimal(reservation.deposit_amount_snapshot) != Decimal(payment.amount):
            payment.status = PAYMENT_STATUS_REQUIRES_REVIEW
            _record_event(payment_session, payment, event_id, event_type)
            _record_outbox_id(outbox_ids, queue_financial_alert(payment_session, payment, "financial_review_required"))
            return "requires_review"
        _record_event(payment_session, payment, event_id, event_type)
        payment.external_payment_id = intent_id
        payment.provider_charge_id = _charge_id(payment_intent) or payment.provider_charge_id
        if reservation.status == RESERVATION_STATUS_CANCELLED:
            # A cancellation must never leave a late card hold behind.  Deposit
            # events do not reactivate the reservation, but a capturable intent
            # still needs a server-to-server cancellation before it is safe.
            if event_type == "payment_intent.canceled":
                if payment.status != PAYMENT_STATUS_RELEASED:
                    payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
                return payment.status
            if event_type == "payment_intent.payment_failed":
                payment.status = PAYMENT_STATUS_AUTHORIZATION_FAILED
                return payment.status
            if event_type == "payment_intent.succeeded":
                _mark_deposit_requires_review(payment_session, payment, outbox_ids)
                return "requires_review"
            if (
                _object_value(payment_intent, "status") == "requires_capture"
                and _cancel_authorized_intent(
                    payment_session,
                    reservation,
                    payment,
                    current_time,
                    outbox_ids,
                    notify_customer=False,
                )
            ):
                return PAYMENT_STATUS_RELEASED
            _mark_deposit_requires_review(payment_session, payment, outbox_ids)
            return "requires_review"
        if event_type == "payment_intent.amount_capturable_updated":
            amount_capturable = _from_cents(_object_value(payment_intent, "amount_capturable"))
            capture_before = _capture_before(payment_intent)
            if (
                _object_value(payment_intent, "status") != "requires_capture"
                or amount_capturable != Decimal(payment.amount)
                or capture_before is None
            ):
                payment.status = PAYMENT_STATUS_REQUIRES_REVIEW
                _record_outbox_id(outbox_ids, queue_financial_alert(payment_session, payment, "financial_review_required"))
                return "requires_review"
            payment.status = PAYMENT_STATUS_AUTHORIZED
            payment.authorized_amount = amount_capturable
            payment.authorized_at = current_time
            payment.capture_before = capture_before
            _record_outbox_id(outbox_ids, queue_deposit_authorized(payment_session, reservation, payment))
            return "authorized"
        if event_type == "payment_intent.succeeded":
            captured_amount = _from_cents(_object_value(payment_intent, "amount_received"))
            if captured_amount is None or captured_amount > Decimal(payment.amount):
                payment.status = PAYMENT_STATUS_REQUIRES_REVIEW
                _record_outbox_id(outbox_ids, queue_financial_alert(payment_session, payment, "financial_review_required"))
                return "requires_review"
            payment.captured_amount = captured_amount
            payment.captured_at = current_time
            payment.paid_at = current_time
            payment.status = PAYMENT_STATUS_CAPTURED if captured_amount == Decimal(payment.amount) else PAYMENT_STATUS_CAPTURED_PARTIALLY
            _record_outbox_id(outbox_ids, queue_deposit_captured(payment_session, reservation, payment))
            return payment.status
        if event_type == "payment_intent.payment_failed":
            payment.status = PAYMENT_STATUS_AUTHORIZATION_FAILED
            _record_outbox_id(outbox_ids, queue_financial_alert(payment_session, payment, "deposit_authorization_failed"))
            return "authorization_failed"
        # A server-side release marks the payment first. An unrelated canceled
        # authorization is an expiry unless Stripe identifies an earlier failure.
        if payment.status != PAYMENT_STATUS_RELEASED:
            payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
            _record_outbox_id(outbox_ids, queue_financial_alert(payment_session, payment, "deposit_authorization_expired"))
        return payment.status


def _get_authorized_deposit(session: Session, reservation_id: int) -> Payment:
    payment = _latest_deposit_payment(session, reservation_id, lock=True)
    if payment is None:
        raise DepositAuthorizationNotFoundError("No existe una fianza para esta reserva.")
    if payment.status != PAYMENT_STATUS_AUTHORIZED or not payment.external_payment_id:
        raise DepositAuthorizationError("La fianza no está autorizada.")
    return payment


def _get_reservation_ready_for_deposit_resolution(
    session: Session, reservation_id: int
) -> Reservation:
    """Lock the returned reservation before releasing or capturing its deposit."""
    reservation = session.execute(
        select(Reservation)
        .where(Reservation.id == reservation_id)
        .with_for_update()
    ).scalar_one_or_none()
    if reservation is None:
        raise DepositAuthorizationNotFoundError("La reserva no existe.")
    if reservation.status != RESERVATION_STATUS_RETURNED_PENDING_CLOSURE:
        raise DepositAuthorizationError(
            "La fianza solo puede resolverse después de registrar la devolución."
        )
    return reservation


def _capture_window_has_expired(payment: Payment, now: datetime) -> bool:
    capture_before = _as_utc(payment.capture_before)
    return capture_before is not None and capture_before <= now


def reconcile_expired_deposit_authorization_for_closure(
    reservation_id: int,
    session: Session | None = None,
    now: datetime | None = None,
) -> Payment:
    """Confirm with Stripe that an elapsed returned-rental hold cannot be captured.

    This never creates a replacement authorization. The existing payment row is
    kept as the financial record and only becomes ``authorization_expired`` when
    Stripe confirms that its PaymentIntent is canceled.
    """
    payment_session = db.session if session is None else session
    current_time = utc_now() if now is None else now
    deferred_error: DepositAuthorizationError | None = None
    reconciled_payment: Payment | None = None

    with payment_session.begin():
        _get_reservation_ready_for_deposit_resolution(payment_session, reservation_id)
        payment = _latest_deposit_payment(payment_session, reservation_id, lock=True)
        if payment is None:
            raise DepositAuthorizationNotFoundError("No existe una fianza para esta reserva.")
        if payment.status == PAYMENT_STATUS_AUTHORIZATION_EXPIRED:
            reconciled_payment = payment
        else:
            if payment.status != PAYMENT_STATUS_AUTHORIZED:
                raise DepositAuthorizationError(
                    "La fianza no está en un estado apto para cerrar sin cargo."
                )
            if not _capture_window_has_expired(payment, current_time):
                raise DepositAuthorizationError("La autorización de fianza sigue vigente.")
            try:
                is_expired = _reconcile_expired_authorization(payment)
            except DepositAuthorizationError:
                payment.status = PAYMENT_STATUS_REQUIRES_REVIEW
                is_expired = False
            if is_expired:
                reconciled_payment = payment
            else:
                deferred_error = DepositAuthorizationError(
                    "Stripe no confirma que la autorización haya caducado; requiere revisión."
                )

    if deferred_error is not None:
        raise deferred_error
    if reconciled_payment is None:
        raise DepositAuthorizationError("No se ha podido reconciliar la autorización de fianza.")
    return reconciled_payment


def release_deposit_authorization(
    reservation_id: int,
    session: Session | None = None,
    now: datetime | None = None,
    outbox_ids: list[int] | None = None,
) -> Payment:
    payment_session = db.session if session is None else session
    current_time = utc_now() if now is None else now
    expired = False
    with payment_session.begin():
        reservation = _get_reservation_ready_for_deposit_resolution(
            payment_session, reservation_id
        )
        payment = _get_authorized_deposit(payment_session, reservation_id)
        if _capture_window_has_expired(payment, current_time):
            payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
            _record_outbox_id(outbox_ids, queue_financial_alert(payment_session, payment, "deposit_authorization_expired"))
            expired = True
        else:
            stripe.api_key = _stripe_secret_key()
            try:
                stripe.PaymentIntent.cancel(payment.external_payment_id)
            except stripe.StripeError as error:
                raise DepositAuthorizationError("Stripe no ha aceptado liberar la fianza.") from error
            payment.status = PAYMENT_STATUS_RELEASED
            payment.released_at = current_time
            _record_outbox_id(outbox_ids, queue_deposit_released(payment_session, reservation, payment))
    if expired:
        raise DepositAuthorizationError("La autorización de fianza ha caducado.")
    return payment


def capture_deposit_authorization(
    reservation_id: int,
    amount: Decimal,
    reason: str,
    session: Session | None = None,
    now: datetime | None = None,
    outbox_ids: list[int] | None = None,
) -> Payment:
    if not reason.strip():
        raise DepositAuthorizationError("El motivo de captura es obligatorio.")
    if amount <= 0:
        raise DepositAuthorizationError("El importe de captura debe ser mayor que cero.")
    payment_session = db.session if session is None else session
    current_time = utc_now() if now is None else now
    expired = False
    with payment_session.begin():
        reservation = _get_reservation_ready_for_deposit_resolution(
            payment_session, reservation_id
        )
        payment = _get_authorized_deposit(payment_session, reservation_id)
        if _capture_window_has_expired(payment, current_time):
            payment.status = PAYMENT_STATUS_AUTHORIZATION_EXPIRED
            _record_outbox_id(outbox_ids, queue_financial_alert(payment_session, payment, "deposit_authorization_expired"))
            expired = True
        else:
            authorized_amount = Decimal(payment.authorized_amount or payment.amount)
            if amount > authorized_amount:
                raise DepositAuthorizationError("El importe supera la fianza actualmente autorizada.")
            stripe.api_key = _stripe_secret_key()
            try:
                intent = stripe.PaymentIntent.capture(
                    payment.external_payment_id,
                    amount_to_capture=_amount_in_cents(amount),
                    final_capture=True,
                )
            except stripe.StripeError as error:
                raise DepositAuthorizationError("Stripe no ha aceptado capturar la fianza.") from error
            captured_amount = _from_cents(_object_value(intent, "amount_received"))
            if _object_value(intent, "status") != "succeeded" or captured_amount != amount:
                raise DepositAuthorizationError("Stripe no ha confirmado el importe de captura.")
            payment.captured_amount = captured_amount
            payment.capture_reason = reason.strip()
            payment.captured_at = current_time
            payment.paid_at = current_time
            payment.status = PAYMENT_STATUS_CAPTURED if amount == Decimal(payment.amount) else PAYMENT_STATUS_CAPTURED_PARTIALLY
            payment.provider_charge_id = _charge_id(intent) or payment.provider_charge_id
            _record_outbox_id(outbox_ids, queue_deposit_captured(payment_session, reservation, payment))
    if expired:
        raise DepositAuthorizationError("La autorización de fianza ha caducado.")
    return payment
