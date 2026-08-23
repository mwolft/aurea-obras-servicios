from decimal import Decimal

from flask import Blueprint, jsonify
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Reservation
from app.services.authentication import get_current_user
from app.services.availability import is_pending_payment_expired


account_bp = Blueprint("account", __name__)


def decimal_to_json(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def serialize_account_reservation(reservation: Reservation) -> dict[str, object]:
    return {
        "id": reservation.id,
        "tool": {"id": reservation.tool.id, "name": reservation.tool.name},
        "start_date": reservation.start_date.isoformat(),
        "end_date": reservation.end_date.isoformat(),
        "status": reservation.status,
        "payment_expired": is_pending_payment_expired(reservation),
        "fulfillment_method": reservation.fulfillment_method,
        "delivery_address": (
            reservation.delivery_address
            if reservation.fulfillment_method == "delivery"
            else None
        ),
        "charged_days": reservation.charged_days,
        "rental_amount": decimal_to_json(reservation.rental_amount),
        "delivery_amount": decimal_to_json(reservation.delivery_amount),
        "total_amount": decimal_to_json(reservation.total_amount),
        "payment_expires_at": (
            reservation.payment_expires_at.isoformat()
            if reservation.payment_expires_at is not None
            else None
        ),
        "created_at": reservation.created_at.isoformat(),
    }


def serialize_account_reservation_detail(reservation: Reservation) -> dict[str, object]:
    """Serialize the reservation data that belongs exclusively to its owner."""
    return {
        "id": reservation.id,
        "tool": {"id": reservation.tool.id, "name": reservation.tool.name},
        "start_date": reservation.start_date.isoformat(),
        "end_date": reservation.end_date.isoformat(),
        "status": reservation.status,
        "payment_expired": is_pending_payment_expired(reservation),
        "fulfillment_method": reservation.fulfillment_method,
        "delivery_address": (
            reservation.delivery_address
            if reservation.fulfillment_method == "delivery"
            else None
        ),
        "billable_km": decimal_to_json(reservation.billable_km),
        "charged_days": reservation.charged_days,
        "daily_price_snapshot": decimal_to_json(reservation.daily_price_snapshot),
        "rental_amount": decimal_to_json(reservation.rental_amount),
        "delivery_price_per_km_snapshot": decimal_to_json(
            reservation.delivery_price_per_km_snapshot
        ),
        "delivery_amount": decimal_to_json(reservation.delivery_amount),
        "total_amount": decimal_to_json(reservation.total_amount),
        "payment_expires_at": (
            reservation.payment_expires_at.isoformat()
            if reservation.payment_expires_at is not None
            else None
        ),
        "created_at": reservation.created_at.isoformat(),
        "customer_name": reservation.customer_name,
        "customer_email": reservation.customer_email,
        "customer_phone": reservation.customer_phone,
    }


@account_bp.get("/reservations")
def list_account_reservations():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    reservations = db.session.execute(
        select(Reservation)
        .where(Reservation.user_id == user.id)
        .options(joinedload(Reservation.tool))
        .order_by(Reservation.created_at.desc(), Reservation.id.desc())
    ).scalars().all()

    return jsonify([serialize_account_reservation(reservation) for reservation in reservations])


@account_bp.get("/reservations/<int:reservation_id>")
def get_account_reservation(reservation_id: int):
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    reservation = db.session.execute(
        select(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.user_id == user.id,
        )
        .options(joinedload(Reservation.tool))
    ).scalar_one_or_none()

    if reservation is None:
        return jsonify({"error": "Reservation not found."}), 404

    return jsonify(serialize_account_reservation_detail(reservation))
