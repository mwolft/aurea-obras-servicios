import re
from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, jsonify, request
from sqlalchemy.orm import selectinload

from app.models import Reservation, Tool
from app.services.availability import is_tool_available
from app.services.cloudinary_storage import get_public_image_url
from app.services.reservations import (
    ReservationToolNotFoundError,
    ReservationFulfillmentUnavailableError,
    ReservationUnavailableError,
    create_reservation,
)
from app.services.authentication import get_authenticated_user_id


tools_bp = Blueprint("tools", __name__)


def decimal_to_json(value: Decimal | None) -> str | None:
    if value is None:
        return None

    return format(value, "f")


def serialize_tool(tool: Tool) -> dict[str, object]:
    return {
        "id": tool.id,
        "name": tool.name,
        "category": tool.category,
        "description": tool.description,
        "daily_price": decimal_to_json(tool.daily_price),
        "deposit_amount": decimal_to_json(tool.deposit_amount),
        "pickup_available": tool.pickup_available,
        "delivery_available": tool.delivery_available,
        "delivery_price_per_km": decimal_to_json(tool.delivery_price_per_km),
        "is_available": tool.is_available,
        "included_km": tool.included_km,
        "extra_km_price": decimal_to_json(tool.extra_km_price),
        "images": [
            {
                "url": get_public_image_url(image.storage_key),
                "position": image.position,
            }
            for image in tool.images
        ],
    }


def parse_iso_date(value: str | None, field_name: str) -> tuple[date | None, tuple[dict[str, str], int] | None]:
    if not value:
        return None, ({"error": f"{field_name} is required."}, 400)

    if not isinstance(value, str):
        return None, ({"error": f"{field_name} must use YYYY-MM-DD format."}, 400)

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None, ({"error": f"{field_name} must use YYYY-MM-DD format."}, 400)

    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, ({"error": f"{field_name} must use YYYY-MM-DD format."}, 400)


def parse_required_text(value: object, field_name: str) -> tuple[str | None, tuple[dict[str, str], int] | None]:
    if not isinstance(value, str) or not value.strip():
        return None, ({"error": f"{field_name} is required."}, 400)

    return value.strip(), None


def parse_email(value: object) -> tuple[str | None, tuple[dict[str, str], int] | None]:
    email, error = parse_required_text(value, "customer_email")
    if error:
        return None, error

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return None, ({"error": "customer_email must be a valid email address."}, 400)

    return email, None


def parse_accepted(value: object, field_name: str) -> tuple[bool | None, tuple[dict[str, str], int] | None]:
    if value is not True:
        return None, ({"error": f"{field_name} must be accepted."}, 400)

    return True, None


def parse_fulfillment_method(value: object) -> tuple[str | None, tuple[dict[str, str], int] | None]:
    if value not in {"pickup", "delivery"}:
        return None, ({"error": "fulfillment_method must be pickup or delivery."}, 400)

    return value, None


def serialize_reservation(reservation: Reservation) -> dict[str, object]:
    return {
        "id": reservation.id,
        "tool_id": reservation.tool_id,
        "start_date": reservation.start_date.isoformat(),
        "end_date": reservation.end_date.isoformat(),
        "status": reservation.status,
        "fulfillment_method": reservation.fulfillment_method,
        "payment_expires_at": (
            reservation.payment_expires_at.isoformat()
            if reservation.payment_expires_at is not None
            else None
        ),
        "charged_days": reservation.charged_days,
        "daily_price_snapshot": decimal_to_json(reservation.daily_price_snapshot),
        "delivery_price_per_km_snapshot": decimal_to_json(
            reservation.delivery_price_per_km_snapshot
        ),
        "rental_amount": decimal_to_json(reservation.rental_amount),
        "delivery_amount": decimal_to_json(reservation.delivery_amount),
        "total_amount": decimal_to_json(reservation.total_amount),
        "deposit_amount": decimal_to_json(reservation.tool.deposit_amount),
    }


@tools_bp.get("")
def list_tools():
    tools = (
        Tool.query.filter_by(is_published=True)
        .options(selectinload(Tool.images))
        .order_by(Tool.name.asc(), Tool.id.asc())
        .all()
    )

    return jsonify([serialize_tool(tool) for tool in tools])


@tools_bp.get("/<int:tool_id>")
def get_tool(tool_id: int):
    tool = (
        Tool.query.options(selectinload(Tool.images))
        .filter_by(id=tool_id, is_published=True)
        .first()
    )

    if tool is None:
        abort(404)

    return jsonify(serialize_tool(tool))


@tools_bp.get("/<int:tool_id>/availability")
def get_tool_availability(tool_id: int):
    tool = Tool.query.filter_by(id=tool_id, is_published=True).first()
    if tool is None:
        abort(404)

    start_date, start_error = parse_iso_date(request.args.get("start_date"), "start_date")
    if start_error:
        return jsonify(start_error[0]), start_error[1]

    end_date, end_error = parse_iso_date(request.args.get("end_date"), "end_date")
    if end_error:
        return jsonify(end_error[0]), end_error[1]

    if end_date < start_date:
        return jsonify({"error": "end_date must be on or after start_date."}), 400

    return jsonify(
        {
            "tool_id": tool.id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "available": is_tool_available(tool, start_date, end_date),
        }
    )


@tools_bp.post("/<int:tool_id>/reservations")
def create_tool_reservation(tool_id: int):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    start_date, start_error = parse_iso_date(payload.get("start_date"), "start_date")
    if start_error:
        return jsonify(start_error[0]), start_error[1]

    end_date, end_error = parse_iso_date(payload.get("end_date"), "end_date")
    if end_error:
        return jsonify(end_error[0]), end_error[1]

    if end_date < start_date:
        return jsonify({"error": "end_date must be on or after start_date."}), 400

    customer_name, customer_name_error = parse_required_text(payload.get("customer_name"), "customer_name")
    if customer_name_error:
        return jsonify(customer_name_error[0]), customer_name_error[1]

    customer_email, customer_email_error = parse_email(payload.get("customer_email"))
    if customer_email_error:
        return jsonify(customer_email_error[0]), customer_email_error[1]

    customer_phone, customer_phone_error = parse_required_text(payload.get("customer_phone"), "customer_phone")
    if customer_phone_error:
        return jsonify(customer_phone_error[0]), customer_phone_error[1]

    terms_accepted, terms_error = parse_accepted(payload.get("terms_accepted"), "terms_accepted")
    if terms_error:
        return jsonify(terms_error[0]), terms_error[1]

    privacy_accepted, privacy_error = parse_accepted(payload.get("privacy_accepted"), "privacy_accepted")
    if privacy_error:
        return jsonify(privacy_error[0]), privacy_error[1]

    fulfillment_method, fulfillment_error = parse_fulfillment_method(payload.get("fulfillment_method"))
    if fulfillment_error:
        return jsonify(fulfillment_error[0]), fulfillment_error[1]

    delivery_address = None
    if fulfillment_method == "delivery":
        delivery_address, delivery_address_error = parse_required_text(
            payload.get("delivery_address"), "delivery_address"
        )
        if delivery_address_error:
            return jsonify(delivery_address_error[0]), delivery_address_error[1]

    try:
        reservation = create_reservation(
            tool_id,
            start_date,
            end_date,
            customer_name,
            customer_email,
            customer_phone,
            terms_accepted,
            privacy_accepted,
            fulfillment_method,
            delivery_address,
            user_id=get_authenticated_user_id(),
        )
    except ReservationToolNotFoundError:
        abort(404)
    except (ReservationUnavailableError, ReservationFulfillmentUnavailableError):
        return jsonify({"error": "La herramienta no está disponible para las fechas seleccionadas."}), 409

    return jsonify(serialize_reservation(reservation)), 201
