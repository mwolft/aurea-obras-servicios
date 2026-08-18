from decimal import Decimal

from flask import Blueprint, abort, jsonify
from sqlalchemy.orm import selectinload

from app.models import Tool
from app.services.cloudinary_storage import get_public_image_url


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
