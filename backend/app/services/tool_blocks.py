"""Controlled operational tool-block management."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Tool, ToolBlock
from app.services.availability import has_blocking_reservation, has_tool_block


class ToolBlockValidationError(Exception):
    """Raised when a block does not contain valid operational data."""


class ToolBlockConflictError(Exception):
    """Raised when a block would overlap an active reservation or another block."""


class ToolBlockNotFoundError(Exception):
    """Raised when a requested block or tool does not exist."""


def _validate_block_data(start_date: date, end_date: date, reason: str) -> str:
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ToolBlockValidationError("Las fechas del bloqueo son obligatorias.")

    if end_date < start_date:
        raise ToolBlockValidationError(
            "La fecha de fin debe ser posterior o igual a la fecha de inicio."
        )

    if not isinstance(reason, str) or not (normalized_reason := reason.strip()):
        raise ToolBlockValidationError("El motivo del bloqueo es obligatorio.")

    if len(normalized_reason) > 255:
        raise ToolBlockValidationError("El motivo del bloqueo no puede superar 255 caracteres.")

    return normalized_reason


def _lock_tools(session: Session, tool_ids: set[int]) -> dict[int, Tool]:
    tools = session.execute(
        select(Tool).where(Tool.id.in_(sorted(tool_ids))).order_by(Tool.id).with_for_update()
    ).scalars().all()
    tools_by_id = {tool.id: tool for tool in tools}
    if len(tools_by_id) != len(tool_ids):
        raise ToolBlockNotFoundError

    return tools_by_id


def _ensure_block_can_be_saved(
    session: Session,
    tool_id: int,
    start_date: date,
    end_date: date,
    exclude_block_id: int | None = None,
) -> None:
    if has_blocking_reservation(session, tool_id, start_date, end_date):
        raise ToolBlockConflictError(
            "El bloqueo se solapa con una reserva que actualmente bloquea disponibilidad."
        )

    if has_tool_block(session, tool_id, start_date, end_date, exclude_block_id):
        raise ToolBlockConflictError("El bloqueo se solapa con otro bloqueo de la herramienta.")


def create_tool_block(
    tool_id: int,
    start_date: date,
    end_date: date,
    reason: str,
    session: Session | None = None,
) -> ToolBlock:
    """Create a block after serializing writes for its tool."""
    block_session = db.session if session is None else session
    normalized_reason = _validate_block_data(start_date, end_date, reason)

    with block_session.begin():
        _lock_tools(block_session, {tool_id})
        _ensure_block_can_be_saved(block_session, tool_id, start_date, end_date)
        block = ToolBlock(
            tool_id=tool_id,
            start_date=start_date,
            end_date=end_date,
            reason=normalized_reason,
        )
        block_session.add(block)
        block_session.flush()

    return block


def update_tool_block(
    block_id: int,
    tool_id: int,
    start_date: date,
    end_date: date,
    reason: str,
    session: Session | None = None,
) -> ToolBlock:
    """Update a block while preserving the same availability guarantees."""
    block_session = db.session if session is None else session
    normalized_reason = _validate_block_data(start_date, end_date, reason)

    with block_session.begin():
        block = (
            block_session.execute(
                select(ToolBlock).where(ToolBlock.id == block_id).with_for_update()
            )
            .scalar_one_or_none()
        )
        if block is None:
            raise ToolBlockNotFoundError

        _lock_tools(block_session, {block.tool_id, tool_id})
        _ensure_block_can_be_saved(
            block_session,
            tool_id,
            start_date,
            end_date,
            exclude_block_id=block.id,
        )
        block.tool_id = tool_id
        block.start_date = start_date
        block.end_date = end_date
        block.reason = normalized_reason
        block_session.flush()

    return block


def delete_tool_block(block_id: int, session: Session | None = None) -> None:
    """Remove one administrative block and immediately release its dates."""
    block_session = db.session if session is None else session

    with block_session.begin():
        block = (
            block_session.execute(
                select(ToolBlock).where(ToolBlock.id == block_id).with_for_update()
            )
            .scalar_one_or_none()
        )
        if block is None:
            raise ToolBlockNotFoundError

        _lock_tools(block_session, {block.tool_id})
        block_session.delete(block)
        block_session.flush()
