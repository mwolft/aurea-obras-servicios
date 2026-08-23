from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.models import Tool


MONEY_QUANTUM = Decimal("0.01")


class QuoteCalculationError(ValueError):
    """Raised when a tool cannot produce a definitive quote for the request."""


@dataclass(frozen=True)
class ReservationQuote:
    charged_days: int
    daily_price_snapshot: Decimal
    delivery_price_per_km_snapshot: Decimal | None
    billable_km: Decimal | None
    rental_amount: Decimal
    delivery_amount: Decimal
    total_amount: Decimal
    deposit_amount: Decimal


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_quote(
    tool: Tool,
    start_date: date,
    end_date: date,
    fulfillment_method: str,
    billable_km: Decimal | None = None,
) -> ReservationQuote:
    """Calculate an authoritative, final quote from tool data and dates only."""
    if end_date < start_date:
        raise QuoteCalculationError("end_date must be on or after start_date.")

    charged_days = (end_date - start_date).days + 1
    daily_price = Decimal(tool.daily_price)
    rental_amount = money(daily_price * charged_days)
    deposit_amount = Decimal(tool.deposit_amount)

    if fulfillment_method == "pickup":
        return ReservationQuote(
            charged_days=charged_days,
            daily_price_snapshot=daily_price,
            delivery_price_per_km_snapshot=None,
            billable_km=None,
            rental_amount=rental_amount,
            delivery_amount=Decimal("0.00"),
            total_amount=rental_amount,
            deposit_amount=deposit_amount,
        )

    if fulfillment_method != "delivery":
        raise QuoteCalculationError("fulfillment_method must be pickup or delivery.")

    if billable_km is None:
        raise QuoteCalculationError("billable_km is required for delivery.")

    if billable_km < 0:
        raise QuoteCalculationError("billable_km must not be negative.")

    if tool.delivery_price_per_km is None:
        raise QuoteCalculationError("The tool has no delivery price per kilometre.")

    delivery_price_per_km = Decimal(tool.delivery_price_per_km)
    delivery_amount = money(billable_km * delivery_price_per_km)

    return ReservationQuote(
        charged_days=charged_days,
        daily_price_snapshot=daily_price,
        delivery_price_per_km_snapshot=delivery_price_per_km,
        billable_km=billable_km,
        rental_amount=rental_amount,
        delivery_amount=delivery_amount,
        total_amount=money(rental_amount + delivery_amount),
        deposit_amount=deposit_amount,
    )
