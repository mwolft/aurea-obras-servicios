import logging

import stripe
from flask import Blueprint, jsonify, request

from app.extensions import db
from app.services.authentication import get_authenticated_user_id
from app.services.stripe_checkout import (
    ReservationPaymentExpiredError,
    ReservationPaymentNotFoundError,
    ReservationPaymentProcessingError,
    ReservationPaymentStateError,
    StripeCheckoutError,
    StripeConfigurationError,
    construct_stripe_event,
    get_stripe_checkout_status,
    process_stripe_event,
    start_or_recover_stripe_checkout,
)
from app.services.paypal_checkout import (
    PayPalCheckoutError,
    PayPalConfigurationError,
    PayPalWebhookVerificationError,
    capture_paypal_order,
    get_paypal_order_status,
    process_paypal_event,
    start_or_recover_paypal_order,
    verify_paypal_webhook,
)
from app.services.deposit_authorizations import (
    DepositAuthorizationError,
    capture_deposit_authorization,
    process_stripe_deposit_event,
    release_deposit_authorization,
    start_or_recover_deposit_checkout,
)
from app.services.email.outbox import deliver_outbox_emails


logger = logging.getLogger(__name__)
payments_bp = Blueprint("payments", __name__)


@payments_bp.post("/reservations/<int:reservation_id>/payments/stripe")
def start_stripe_payment(reservation_id: int):
    try:
        # The service owns the transaction and row locks. Clear any scoped
        # read transaction opened earlier in the request before entering it.
        db.session.rollback()
        checkout_url = start_or_recover_stripe_checkout(
            reservation_id, get_authenticated_user_id()
        )
    except ReservationPaymentNotFoundError:
        return jsonify({"error": "Reservation not found."}), 404
    except ReservationPaymentExpiredError:
        return jsonify({"error": "La ventana de pago ha caducado."}), 409
    except ReservationPaymentProcessingError:
        return jsonify({"error": "Hay un pago en curso o pendiente de revisión. Espera antes de elegir otro método."}), 409
    except ReservationPaymentStateError:
        return jsonify({"error": "La reserva no se puede pagar en este estado."}), 409
    except StripeConfigurationError:
        logger.exception("Stripe payment initiation is not configured.")
        return jsonify({"error": "El pago no está disponible en este momento."}), 503
    except StripeCheckoutError:
        logger.exception("Stripe Checkout could not be started.")
        return jsonify({"error": "No se ha podido iniciar el pago. Inténtalo de nuevo."}), 502

    return jsonify({"checkout_url": checkout_url})


@payments_bp.get("/payments/stripe/sessions/<string:external_payment_id>")
def get_stripe_payment_status(external_payment_id: str):
    status = get_stripe_checkout_status(external_payment_id)
    if status is None:
        return jsonify({"error": "Payment not found."}), 404
    return jsonify(status)


@payments_bp.post("/payments/stripe/webhook")
def stripe_webhook():
    try:
        event = construct_stripe_event(
            request.get_data(cache=True, as_text=False), request.headers.get("Stripe-Signature")
        )
    except StripeConfigurationError:
        logger.exception("Stripe webhook is not configured.")
        return jsonify({"error": "Webhook is not configured."}), 503
    except (ValueError, stripe.SignatureVerificationError):
        return jsonify({"error": "Invalid Stripe signature."}), 400

    # The domain service owns its transaction for the idempotent transition.
    db.session.rollback()
    outbox_ids: list[int] = []
    outcome = process_stripe_deposit_event(event, outbox_ids=outbox_ids)
    if outcome == "ignored":
        outcome = process_stripe_event(event, outbox_ids=outbox_ids)
    deliver_outbox_emails(outbox_ids)
    return jsonify({"status": outcome})


@payments_bp.post("/reservations/<int:reservation_id>/deposit/stripe")
def start_reservation_deposit(reservation_id: int):
    """Start a card-only deposit authorization for the owning user.

    Admin uses the same service through its controlled reservation action.
    """
    from app.services.authentication import get_current_user

    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401
    try:
        db.session.rollback()
        # A non-admin client may only initiate a deposit for their own reservation.
        checkout_url = start_or_recover_deposit_checkout(
            reservation_id, user_id=user.id, is_admin=user.is_admin
        )
    except ReservationPaymentNotFoundError:
        return jsonify({"error": "Reservation not found."}), 404
    except ReservationPaymentStateError as error:
        return jsonify({"error": str(error)}), 409
    except StripeConfigurationError:
        logger.exception("Stripe deposit authorization is not configured.")
        return jsonify({"error": "La fianza no está disponible en este momento."}), 503
    except (StripeCheckoutError, DepositAuthorizationError):
        logger.exception("Stripe deposit authorization could not be started.")
        return jsonify({"error": "No se ha podido iniciar la autorización de fianza."}), 502
    return jsonify({"checkout_url": checkout_url})


@payments_bp.post("/reservations/<int:reservation_id>/payments/paypal")
def start_paypal_payment(reservation_id: int):
    try:
        db.session.rollback()
        approval_url = start_or_recover_paypal_order(
            reservation_id, get_authenticated_user_id()
        )
    except ReservationPaymentNotFoundError:
        return jsonify({"error": "Reservation not found."}), 404
    except ReservationPaymentExpiredError:
        return jsonify({"error": "La ventana de pago ha caducado."}), 409
    except ReservationPaymentProcessingError:
        return jsonify({"error": "Hay un pago en curso o pendiente de revisión. Espera antes de elegir otro método."}), 409
    except ReservationPaymentStateError:
        return jsonify({"error": "La reserva no se puede pagar en este estado."}), 409
    except PayPalConfigurationError:
        logger.exception("PayPal payment initiation is not configured.")
        return jsonify({"error": "El pago no está disponible en este momento."}), 503
    except PayPalCheckoutError:
        logger.exception("PayPal Order could not be started.")
        return jsonify({"error": "No se ha podido iniciar el pago. Inténtalo de nuevo."}), 502
    return jsonify({"approval_url": approval_url})


@payments_bp.post("/payments/paypal/orders/<string:external_payment_id>/capture")
def capture_paypal_payment(external_payment_id: str):
    try:
        db.session.rollback()
        outcome = capture_paypal_order(external_payment_id, get_authenticated_user_id())
    except ReservationPaymentNotFoundError:
        return jsonify({"error": "Payment not found."}), 404
    except ReservationPaymentExpiredError:
        return jsonify({"error": "La ventana de pago ha caducado."}), 409
    except ReservationPaymentStateError:
        return jsonify({"error": "La reserva no se puede pagar en este estado."}), 409
    except PayPalConfigurationError:
        logger.exception("PayPal capture is not configured.")
        return jsonify({"error": "El pago no está disponible en este momento."}), 503
    except PayPalCheckoutError:
        logger.exception("PayPal Order could not be captured.")
        return jsonify({"error": "No se ha podido completar el pago. Inténtalo de nuevo."}), 502
    return jsonify({"status": outcome})


@payments_bp.get("/payments/paypal/orders/<string:external_payment_id>")
def get_paypal_payment_status(external_payment_id: str):
    status = get_paypal_order_status(external_payment_id, get_authenticated_user_id())
    if status is None:
        return jsonify({"error": "Payment not found."}), 404
    return jsonify(status)


@payments_bp.post("/payments/paypal/webhook")
def paypal_webhook():
    event = request.get_json(silent=True)
    if not isinstance(event, dict):
        return jsonify({"error": "Invalid PayPal webhook."}), 400
    try:
        if not verify_paypal_webhook(event, request.headers):
            return jsonify({"error": "Invalid PayPal signature."}), 400
    except PayPalConfigurationError:
        logger.exception("PayPal webhook is not configured.")
        return jsonify({"error": "Webhook is not configured."}), 503
    except PayPalWebhookVerificationError:
        logger.exception("PayPal webhook verification failed.")
        return jsonify({"error": "Webhook verification failed."}), 502
    db.session.rollback()
    outbox_ids: list[int] = []
    outcome = process_paypal_event(event, outbox_ids=outbox_ids)
    deliver_outbox_emails(outbox_ids)
    return jsonify({"status": outcome})
