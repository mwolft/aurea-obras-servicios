"""Read-only operational agenda queries for Flask-Admin."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.extensions import db
from app.models import Reservation, ToolBlock
from app.services.availability import inclusive_date_range_conditions, reservation_status_label


@dataclass(frozen=True)
class AgendaEvent:
    type: str
    id: int
    tool_id: int
    tool_name: str
    start_date: date
    end_date: date
    status: str | None = None
    status_label: str | None = None
    customer_name: str | None = None
    fulfillment_method: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class AgendaToolGroup:
    tool_id: int
    tool_name: str
    events: tuple[AgendaEvent, ...]


def get_agenda_events(
    start_date: date,
    end_date: date,
    tool_id: int | None = None,
    session: Session | None = None,
) -> list[AgendaEvent]:
    """Return reservations and administrative blocks overlapping an inclusive range."""
    agenda_session = db.session if session is None else session

    reservations_query = (
        select(Reservation)
        .options(joinedload(Reservation.tool))
        .where(*inclusive_date_range_conditions(Reservation, start_date, end_date))
    )
    blocks_query = (
        select(ToolBlock)
        .options(joinedload(ToolBlock.tool))
        .where(*inclusive_date_range_conditions(ToolBlock, start_date, end_date))
    )
    if tool_id is not None:
        reservations_query = reservations_query.where(Reservation.tool_id == tool_id)
        blocks_query = blocks_query.where(ToolBlock.tool_id == tool_id)

    reservations = agenda_session.execute(reservations_query).scalars().all()
    blocks = agenda_session.execute(blocks_query).scalars().all()

    events = [
        AgendaEvent(
            type="reservation",
            id=reservation.id,
            tool_id=reservation.tool_id,
            tool_name=reservation.tool.name,
            start_date=reservation.start_date,
            end_date=reservation.end_date,
            status=reservation.status,
            status_label=reservation_status_label(reservation),
            customer_name=reservation.customer_name,
            fulfillment_method=reservation.fulfillment_method,
        )
        for reservation in reservations
    ]
    events.extend(
        AgendaEvent(
            type="tool_block",
            id=block.id,
            tool_id=block.tool_id,
            tool_name=block.tool.name,
            start_date=block.start_date,
            end_date=block.end_date,
            status_label="Bloqueo administrativo",
            reason=block.reason,
        )
        for block in blocks
    )

    return sorted(
        events,
        key=lambda event: (
            event.tool_name.casefold(),
            event.tool_id,
            event.start_date,
            event.end_date,
            event.id,
            event.type,
        ),
    )


def group_agenda_events(events: list[AgendaEvent]) -> list[AgendaToolGroup]:
    """Group the already stable event list by tool without issuing more queries."""
    groups: list[AgendaToolGroup] = []
    current_tool_id: int | None = None
    current_tool_name = ""
    current_events: list[AgendaEvent] = []

    for event in events:
        if event.tool_id != current_tool_id:
            if current_tool_id is not None:
                groups.append(
                    AgendaToolGroup(current_tool_id, current_tool_name, tuple(current_events))
                )
            current_tool_id = event.tool_id
            current_tool_name = event.tool_name
            current_events = []
        current_events.append(event)

    if current_tool_id is not None:
        groups.append(AgendaToolGroup(current_tool_id, current_tool_name, tuple(current_events)))

    return groups
