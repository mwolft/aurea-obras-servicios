"""PayPal Orders integration for the shared rental payment domain.

The browser can approve an Order and ask this server to capture it, but it can
never transition a reservation itself. A verified PayPal webhook performs the
only confirmation transition.
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import requests
from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Payment, Reservation, Tool
from app.services.availability import is_pending_payment_expired, utc_now
from app.services.payment_domain import (
    PAYMENT_PROVIDER_PAYPAL,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_REQUIRES_REVIEW,
    RESERVATION_STATUS_CONFIRMED,
    RESERVATION_STATUS_PENDING_PAYMENT,
    serialize_payment_return_reservation,
)
from app.services.stripe_checkout import (
    ReservationPaymentExpiredError,
    ReservationPaymentNotFoundError,
    ReservationPaymentStateError,
)
from app.services.email.rental import queue_financial_alert, queue_reservation_confirmed


logger = logging.getLogger(__name__)
PAYPAL_CURRENCY = "EUR"
PAYPAL_TIMEOUT_SECONDS = 10
PAYPAL_COMPLETED_EVENT = "PAYMENT.CAPTURE.COMPLETED"


class PayPalConfigurationError(RuntimeError):
    """Raised when PayPal credentials or environment are incomplete."""


class PayPalCheckoutError(RuntimeError):
    """Raised when PayPal cannot create, retrieve, or capture an Order."""


class PayPalWebhookVerificationError(RuntimeError):
    """Raised when an incoming PayPal webhook cannot be authenticated."""


def _paypal_base_url() -> str:
    environment = current_app.config.get("PAYPAL_ENVIRONMENT", "sandbox")
    if environment == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    if environment == "live":
        return "https://api-m.paypal.com"
    raise PayPalConfigurationError("PAYPAL_ENVIRONMENT must be sandbox or live.")


def _paypal_credentials() -> tuple[str, str]:
    client_id = current_app.config.get("PAYPAL_CLIENT_ID")
    client_secret = current_app.config.get("PAYPAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise PayPalConfigurationError("PayPal is not configured.")
    return client_id, client_secret


def _paypal_webhook_id() -> str:
    webhook_id = current_app.config.get("PAYPAL_WEBHOOK_ID")
    if not webhook_id:
        raise PayPalConfigurationError("PayPal webhook verification is not configured.")
    return webhook_id


def _access_token() -> str:
    client_id, client_secret = _paypal_credentials()
    try:
        response = requests.post(
            f"{_paypal_base_url()}/v1/oauth2/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json", "Accept-Language": "es_ES"},
            timeout=PAYPAL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
    except (requests.RequestException, ValueError) as error:
        raise PayPalCheckoutError("PayPal authentication failed.") from error
    if not isinstance(token, str) or not token:
        raise PayPalCheckoutError("PayPal did not return an access token.")
    return token


def _authorization_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _amount_value(amount: Decimal) -> str:
    return f"{Decimal(amount):.2f}"


def _assert_reservation_can_start_payment(reservation: Reservation, now: datetime) -> None:
    if reservation.status != RESERVATION_STATUS_PENDING_PAYMENT:
        raise ReservationPaymentStateError("The reservation is not pending payment.")
    if is_pending_payment_expired(reservation, now):
        raise ReservationPaymentExpiredError("The payment window has expired.")
    if reservation.total_amount is None:
        raise ReservationPaymentStateError("The reservation does not have a final total.")


def _return_urls(reservation: Reservation) -> tuple[str, str]:
    origin = current_app.config["FRONTEND_ORIGIN"].rstrip("/")
    tool_url = f"{origin}/alquiler/{reservation.tool_id}"
    return (
        f"{origin}/reserva/confirmada?provider=paypal",
        f"{tool_url}?payment=paypal_cancelled",
    )


def _approval_url(order: dict[str, Any]) -> str:
    for link in order.get("links", []):
        if link.get("rel") in {"payer-action", "approve"} and isinstance(link.get("href"), str):
            return link["href"]
    raise PayPalCheckoutError("PayPal did not return an approval URL.")


def _create_order(payment: Payment, reservation: Reservation, tool: Tool) -> dict[str, Any]:
    return_url, cancel_url = _return_urls(reservation)
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": str(payment.id),
                "custom_id": str(payment.id),
                "description": f"Alquiler: {tool.name}",
                "amount": {"currency_code": PAYPAL_CURRENCY, "value": _amount_value(payment.amount)},
            }
        ],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                    "user_action": "PAY_NOW",
                    "shipping_preference": "NO_SHIPPING",
                }
            }
        },
    }
    try:
        response = requests.post(
            f"{_paypal_base_url()}/v2/checkout/orders",
            headers={**_authorization_headers(_access_token()), "PayPal-Request-Id": payment.idempotency_key},
            json=payload,
            timeout=PAYPAL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        order = response.json()
    except (requests.RequestException, ValueError) as error:
        raise PayPalCheckoutError("PayPal could not create an Order.") from error
    if not isinstance(order, dict) or not isinstance(order.get("id"), str):
        raise PayPalCheckoutError("PayPal did not return an Order ID.")
    return order


def _get_order(external_payment_id: str) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{_paypal_base_url()}/v2/checkout/orders/{external_payment_id}",
            headers=_authorization_headers(_access_token()),
            timeout=PAYPAL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        order = response.json()
    except (requests.RequestException, ValueError) as error:
        raise PayPalCheckoutError("PayPal Order could not be retrieved.") from error
    if not isinstance(order, dict):
        raise PayPalCheckoutError("PayPal returned an invalid Order.")
    return order


def start_or_recover_paypal_order(
    reservation_id: int, user_id: int | None, session: Session | None = None, now: datetime | None = None
) -> str:
    """Create at most one active PayPal Order for an eligible reservation."""
    payment_session = db.session if session is None else session
    current_time = utc_now() if now is None else now
    with payment_session.begin():
        reservation = payment_session.execute(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        ).scalar_one_or_none()
        if reservation is None or (reservation.user_id is not None and reservation.user_id != user_id):
            raise ReservationPaymentNotFoundError
        _assert_reservation_can_start_payment(reservation, current_time)
        other_pending = payment_session.execute(
            select(Payment.id).where(
                Payment.reservation_id == reservation.id,
                Payment.provider != PAYMENT_PROVIDER_PAYPAL,
                Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
                Payment.status == PAYMENT_STATUS_PENDING,
            ).with_for_update()
        ).scalar_one_or_none()
        if other_pending is not None:
            raise ReservationPaymentStateError("Another payment method is already active.")
        tool = payment_session.get(Tool, reservation.tool_id)
        payment = payment_session.execute(
            select(Payment).where(
                Payment.reservation_id == reservation.id,
                Payment.provider == PAYMENT_PROVIDER_PAYPAL,
                Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
                Payment.status == PAYMENT_STATUS_PENDING,
            ).with_for_update()
        ).scalar_one_or_none()
        if payment is None:
            payment = Payment(
                reservation_id=reservation.id,
                provider=PAYMENT_PROVIDER_PAYPAL,
                purpose=PAYMENT_PURPOSE_RENTAL_CHARGE,
                status=PAYMENT_STATUS_PENDING,
                amount=Decimal(reservation.total_amount),
                currency=PAYPAL_CURRENCY,
                idempotency_key=uuid.uuid4().hex,
                expires_at=reservation.payment_expires_at,
            )
            payment_session.add(payment)
            payment_session.flush()
        if payment.external_payment_id:
            return _approval_url(_get_order(payment.external_payment_id))
        order = _create_order(payment, reservation, tool)
        payment.external_payment_id = order["id"]
        return _approval_url(order)


def capture_paypal_order(external_payment_id: str, user_id: int | None) -> str:
    """Ask PayPal to capture an approved Order without confirming the reservation."""
    with db.session.begin():
        payment, reservation = _get_payment_and_reservation_for_browser(external_payment_id, user_id, lock=True)
        _assert_reservation_can_start_payment(reservation, utc_now())
        if payment.status != PAYMENT_STATUS_PENDING:
            raise ReservationPaymentStateError("The payment is no longer pending.")
        try:
            response = requests.post(
                f"{_paypal_base_url()}/v2/checkout/orders/{external_payment_id}/capture",
                headers={**_authorization_headers(_access_token()), "PayPal-Request-Id": f"capture-{payment.idempotency_key}"},
                json={},
                timeout=PAYPAL_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise PayPalCheckoutError("PayPal could not capture the Order.") from error
    return "capture_requested"


def _get_payment_and_reservation_for_browser(external_payment_id: str, user_id: int | None, *, lock: bool = False) -> tuple[Payment, Reservation]:
    statement = select(Payment, Reservation).join(Reservation, Reservation.id == Payment.reservation_id).where(
        Payment.provider == PAYMENT_PROVIDER_PAYPAL, Payment.external_payment_id == external_payment_id
        , Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE
    )
    if lock:
        statement = statement.with_for_update()
    row = db.session.execute(statement).one_or_none()
    if row is None:
        raise ReservationPaymentNotFoundError
    payment, reservation = row
    if reservation.user_id is not None and reservation.user_id != user_id:
        raise ReservationPaymentNotFoundError
    return payment, reservation


def get_paypal_order_status(external_payment_id: str, user_id: int | None) -> dict[str, object] | None:
    try:
        payment, reservation = _get_payment_and_reservation_for_browser(external_payment_id, user_id)
    except ReservationPaymentNotFoundError:
        return None
    return {
        "payment_status": payment.status,
        "reservation_status": reservation.status,
        "payment_expired": is_pending_payment_expired(reservation),
        "reservation": serialize_payment_return_reservation(reservation),
    }


def verify_paypal_webhook(payload: dict[str, Any], headers: Any) -> bool:
    required_headers = {
        "auth_algo": headers.get("PayPal-Auth-Algo"),
        "cert_url": headers.get("PayPal-Cert-Url"),
        "transmission_id": headers.get("PayPal-Transmission-Id"),
        "transmission_sig": headers.get("PayPal-Transmission-Sig"),
        "transmission_time": headers.get("PayPal-Transmission-Time"),
    }
    if not all(required_headers.values()):
        return False
    verification_payload = {**required_headers, "webhook_id": _paypal_webhook_id(), "webhook_event": payload}
    try:
        response = requests.post(
            f"{_paypal_base_url()}/v1/notifications/verify-webhook-signature",
            headers=_authorization_headers(_access_token()),
            json=verification_payload,
            timeout=PAYPAL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json().get("verification_status") == "SUCCESS"
    except (requests.RequestException, ValueError) as error:
        raise PayPalWebhookVerificationError("PayPal webhook verification failed.") from error


def _record_outbox_id(outbox_ids: list[int] | None, email) -> None:
    if outbox_ids is not None and email is not None:
        outbox_ids.append(email.id)


def _mark_for_review(
    session: Session, payment: Payment, event_id: str, outbox_ids: list[int] | None
) -> None:
    payment.status = PAYMENT_STATUS_REQUIRES_REVIEW
    payment.provider_event_id = event_id
    _record_outbox_id(outbox_ids, queue_financial_alert(session, payment, "financial_review_required"))


def process_paypal_event(
    event: dict[str, Any],
    session: Session | None = None,
    now: datetime | None = None,
    outbox_ids: list[int] | None = None,
) -> str:
    """Process a verified completed capture and confirm exactly once."""
    if event.get("event_type") != PAYPAL_COMPLETED_EVENT:
        return "ignored"
    event_id = event.get("id")
    resource = event.get("resource")
    if not isinstance(event_id, str) or not isinstance(resource, dict):
        return "requires_review"
    related_ids = resource.get("supplementary_data", {}).get("related_ids", {})
    external_payment_id = related_ids.get("order_id") if isinstance(related_ids, dict) else None
    amount = resource.get("amount")
    if not isinstance(external_payment_id, str) or not isinstance(amount, dict) or resource.get("status") != "COMPLETED":
        return "requires_review"
    payment_session = db.session if session is None else session
    current_time = utc_now() if now is None else now
    with payment_session.begin():
        payment = payment_session.execute(
            select(Payment).where(
                Payment.provider == PAYMENT_PROVIDER_PAYPAL,
                Payment.external_payment_id == external_payment_id,
                Payment.purpose == PAYMENT_PURPOSE_RENTAL_CHARGE,
            ).with_for_update()
        ).scalar_one_or_none()
        if payment is None:
            logger.error("PayPal capture does not match a known Order.")
            return "requires_review"
        if payment.provider_event_id == event_id or payment.status == PAYMENT_STATUS_PAID:
            return "duplicate"
        reservation = payment_session.execute(
            select(Reservation).where(Reservation.id == payment.reservation_id).with_for_update()
        ).scalar_one()
        try:
            amount_matches = Decimal(str(amount.get("value"))) == Decimal(payment.amount)
        except Exception:
            amount_matches = False
        if (
            not amount_matches
            or amount.get("currency_code") != PAYPAL_CURRENCY
            or payment.currency != PAYPAL_CURRENCY
            or reservation.total_amount is None
            or Decimal(reservation.total_amount) != Decimal(payment.amount)
        ):
            logger.error("PayPal capture amount or currency does not match its reservation snapshot.")
            _mark_for_review(payment_session, payment, event_id, outbox_ids)
            return "requires_review"
        if reservation.status != RESERVATION_STATUS_PENDING_PAYMENT or is_pending_payment_expired(reservation, current_time):
            logger.warning("PayPal capture arrived after its reservation payment window.")
            _mark_for_review(payment_session, payment, event_id, outbox_ids)
            return "requires_review"
        payment.status = PAYMENT_STATUS_PAID
        payment.provider_event_id = event_id
        payment.paid_at = current_time
        reservation.status = RESERVATION_STATUS_CONFIRMED
        _record_outbox_id(outbox_ids, queue_reservation_confirmed(payment_session, reservation))
        return "confirmed"
