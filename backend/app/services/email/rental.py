"""Rental-specific transactional email content and outbox helpers."""

from datetime import datetime, timezone
from decimal import Decimal

from flask import current_app
from sqlalchemy.orm import Session

from app.models import Payment, Reservation

from .base import EmailContent, action_button, information_block, information_row, message_block, render_email
from .outbox import internal_alert_recipient, queue_transactional_email


EVENT_RESERVATION_CONFIRMED = "reservation_confirmed"
EVENT_RESERVATION_PENDING_REVIEW_CUSTOMER = "reservation_pending_review_customer"
EVENT_RESERVATION_PENDING_REVIEW_ADMIN = "reservation_pending_review_admin"
EVENT_RESERVATION_PENDING_PAYMENT = "reservation_pending_payment"
EVENT_RESERVATION_CANCELLED = "reservation_cancelled"
EVENT_DEPOSIT_AUTHORIZED = "deposit_authorized"
EVENT_DEPOSIT_RELEASED = "deposit_released"
EVENT_DEPOSIT_CAPTURED = "deposit_captured"
EVENT_RESERVATION_DELIVERED = "reservation_delivered"
EVENT_RESERVATION_RETURNED = "reservation_returned"
EVENT_RESERVATION_COMPLETED = "reservation_completed"
EVENT_FINANCIAL_REVIEW = "financial_review_required"
EVENT_DEPOSIT_FAILED = "deposit_authorization_failed"
EVENT_DEPOSIT_EXPIRED = "deposit_authorization_expired"


def _format_date(value) -> str:
    return value.strftime("%d/%m/%Y")


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


def _format_amount(value: Decimal | None) -> str:
    return f"{Decimal(value or 0):.2f} €"


def _tool_name(reservation: Reservation) -> str:
    return reservation.tool.name if reservation.tool is not None else "Herramienta reservada"


def _reservation_rows(reservation: Reservation, *, include_total: bool = False, include_deposit: bool = False) -> str:
    rows = information_row("Cliente", reservation.customer_name or "Cliente")
    rows += information_row("Herramienta", _tool_name(reservation))
    rows += information_row("Fechas", f"{_format_date(reservation.start_date)} — {_format_date(reservation.end_date)}")
    rows += information_row("Modalidad", "Entrega" if reservation.fulfillment_method == "delivery" else "Recogida")
    if reservation.fulfillment_method == "delivery" and reservation.delivery_address:
        rows += information_row("Dirección", reservation.delivery_address)
    if include_total:
        rows += information_row("Total pagado", _format_amount(reservation.total_amount))
    if include_deposit:
        rows += information_row("Fianza", _format_amount(reservation.deposit_amount_snapshot))
    return rows


def _reservation_text(reservation: Reservation, *, include_total: bool = False, include_deposit: bool = False) -> list[str]:
    lines = [
        f"Cliente: {reservation.customer_name or 'Cliente'}",
        f"Herramienta: {_tool_name(reservation)}",
        f"Fechas: {_format_date(reservation.start_date)} — {_format_date(reservation.end_date)}",
        f"Modalidad: {'Entrega' if reservation.fulfillment_method == 'delivery' else 'Recogida'}",
    ]
    if reservation.fulfillment_method == "delivery" and reservation.delivery_address:
        lines.append(f"Dirección: {reservation.delivery_address}")
    if include_total:
        lines.append(f"Total pagado: {_format_amount(reservation.total_amount)}")
    if include_deposit:
        lines.append(f"Fianza: {_format_amount(reservation.deposit_amount_snapshot)}")
    return lines


def _build_email(
    *,
    title: str,
    preheader: str,
    rows: str,
    text_lines: list[str],
    message: str,
    footer: str,
    action_label: str | None = "Contactar con AUREA",
    action_url: str | None = None,
) -> EmailContent:
    contact_url = f"{current_app.config['FRONTEND_ORIGIN'].rstrip('/')}/contacto"
    resolved_action_url = (action_url or contact_url) if action_label else None
    action_html = (
        action_button(action_label, resolved_action_url)
        if action_label and resolved_action_url
        else ""
    )
    html = render_email(
        title=title,
        preheader=preheader,
        body_html=(
            information_block(rows)
            + message_block("Información", message)
            + action_html
        ),
        footer_text=footer,
    )
    text_parts = [title, "", *text_lines, "", message, "", footer]
    if action_label and resolved_action_url:
        text_parts.append(f"{action_label}: {resolved_action_url}")
    text = "\n".join(text_parts)
    return EmailContent(html=html, text=text)


def _queue_customer(
    session: Session,
    reservation: Reservation,
    *,
    event_type: str,
    idempotency_key: str,
    subject: str,
    content: EmailContent,
):
    return queue_transactional_email(
        session,
        event_type=event_type,
        idempotency_key=idempotency_key,
        recipient=reservation.customer_email,
        subject=subject,
        content=content,
        reservation_id=reservation.id,
    )


def _customer_reservation_url(reservation: Reservation) -> str:
    return f"{current_app.config['FRONTEND_ORIGIN'].rstrip('/')}/mi-cuenta/reservas/{reservation.id}"


def _admin_reservation_url(reservation: Reservation) -> str | None:
    origin = current_app.config.get("BACKEND_ORIGIN")
    if not isinstance(origin, str) or not origin.strip():
        return None
    return f"{origin.rstrip('/')}/admin/reservation/details/?id={reservation.id}"


def _delivery_review_rows(reservation: Reservation, *, include_customer: bool) -> str:
    rows = ""
    if include_customer:
        rows += information_row("Cliente", reservation.customer_name or "Cliente")
    rows += information_row("Referencia", f"#{reservation.id}")
    rows += information_row("Herramienta", _tool_name(reservation))
    rows += information_row("Fechas", f"{_format_date(reservation.start_date)} — {_format_date(reservation.end_date)}")
    rows += information_row("Modalidad", "Entrega")
    if reservation.delivery_address:
        rows += information_row("Dirección", reservation.delivery_address)
    if reservation.billable_km is not None:
        rows += information_row("Kilómetros", f"{reservation.billable_km} km")
    return rows


def _delivery_review_text(reservation: Reservation, *, include_customer: bool) -> list[str]:
    lines = []
    if include_customer:
        lines.append(f"Cliente: {reservation.customer_name or 'Cliente'}")
    lines.extend(
        [
            f"Referencia: #{reservation.id}",
            f"Herramienta: {_tool_name(reservation)}",
            f"Fechas: {_format_date(reservation.start_date)} — {_format_date(reservation.end_date)}",
            "Modalidad: Entrega",
        ]
    )
    if reservation.delivery_address:
        lines.append(f"Dirección: {reservation.delivery_address}")
    if reservation.billable_km is not None:
        lines.append(f"Kilómetros: {reservation.billable_km} km")
    return lines


def queue_delivery_review_requested(session: Session, reservation: Reservation):
    """Queue the customer acknowledgement and the separate Admin alert."""

    customer_email = _queue_customer(
        session,
        reservation,
        event_type=EVENT_RESERVATION_PENDING_REVIEW_CUSTOMER,
        idempotency_key=f"reservation:{reservation.id}:pending_review:customer",
        subject="Hemos recibido tu solicitud de reserva · AUREA",
        content=_build_email(
            title="Hemos recibido tu solicitud de reserva",
            preheader="Revisaremos el transporte antes de que realices el pago.",
            rows=_delivery_review_rows(reservation, include_customer=False),
            text_lines=_delivery_review_text(reservation, include_customer=False),
            message=(
                "AUREA revisará el kilometraje y el importe del transporte. "
                "Todavía no debes realizar ningún pago. Te enviaremos otro correo "
                "cuando la reserva esté lista para continuar."
            ),
            footer="Solicitud de transporte recibida por AUREA Obras y Servicios.",
        ),
    )
    admin_url = _admin_reservation_url(reservation)
    admin_email = queue_transactional_email(
        session,
        event_type=EVENT_RESERVATION_PENDING_REVIEW_ADMIN,
        idempotency_key=f"reservation:{reservation.id}:pending_review:admin",
        recipient=internal_alert_recipient(),
        subject="Nueva reserva pendiente de revisar transporte · AUREA",
        content=_build_email(
            title="Nueva reserva pendiente de revisar transporte",
            preheader="Una solicitud de entrega requiere revisión administrativa.",
            rows=_delivery_review_rows(reservation, include_customer=True),
            text_lines=_delivery_review_text(reservation, include_customer=True),
            message="Revisa el kilometraje y prepara el importe final antes de habilitar el pago.",
            footer="Alerta interna de AUREA Obras y Servicios.",
            action_label="Revisar reserva" if admin_url else None,
            action_url=admin_url,
        ),
        reservation_id=reservation.id,
    )
    return customer_email, admin_email


def queue_delivery_review_completed(session: Session, reservation: Reservation):
    payment_url = _customer_reservation_url(reservation)
    rows = _delivery_review_rows(reservation, include_customer=False)
    rows += information_row("Tarifa aplicada", f"{_format_amount(reservation.delivery_price_per_km_snapshot)}/km")
    rows += information_row("Importe de transporte", _format_amount(reservation.delivery_amount))
    rows += information_row("Importe de alquiler", _format_amount(reservation.rental_amount))
    rows += information_row("Total final", _format_amount(reservation.total_amount))
    rows += information_row("Límite de pago", _format_datetime(reservation.payment_expires_at))
    text_lines = _delivery_review_text(reservation, include_customer=False)
    text_lines.extend(
        [
            f"Tarifa aplicada: {_format_amount(reservation.delivery_price_per_km_snapshot)}/km",
            f"Importe de transporte: {_format_amount(reservation.delivery_amount)}",
            f"Importe de alquiler: {_format_amount(reservation.rental_amount)}",
            f"Total final: {_format_amount(reservation.total_amount)}",
            f"Límite de pago: {_format_datetime(reservation.payment_expires_at)}",
        ]
    )
    return _queue_customer(
        session,
        reservation,
        event_type=EVENT_RESERVATION_PENDING_PAYMENT,
        idempotency_key=f"reservation:{reservation.id}:pending_payment",
        subject="Tu reserva está lista para pagar · AUREA",
        content=_build_email(
            title="Tu reserva está lista para pagar",
            preheader="El transporte ha sido revisado y puedes completar tu reserva.",
            rows=rows,
            text_lines=text_lines,
            message=(
                "Hemos validado el kilometraje, el transporte y el importe final. "
                "Completa el pago antes de la fecha límite para confirmar tu reserva."
            ),
            footer="Reserva lista para pago enviada por AUREA Obras y Servicios.",
            action_label="Completar reserva",
            action_url=payment_url,
        ),
    )


def queue_reservation_confirmed(session: Session, reservation: Reservation):
    return _queue_customer(
        session, reservation,
        event_type=EVENT_RESERVATION_CONFIRMED,
        idempotency_key=f"reservation:{reservation.id}:confirmed",
        subject="Reserva confirmada · AUREA",
        content=_build_email(
            title="Reserva confirmada",
            preheader="Tu pago ha sido confirmado.",
            rows=_reservation_rows(reservation, include_total=True, include_deposit=True),
            text_lines=_reservation_text(reservation, include_total=True, include_deposit=True),
            message="Hemos confirmado tu reserva. La fianza, si corresponde, se gestiona por separado en el momento de la entrega.",
            footer="Confirmación de reserva enviada por AUREA Obras y Servicios.",
        ),
    )


def queue_reservation_cancelled(session: Session, reservation: Reservation):
    return _queue_customer(
        session, reservation,
        event_type=EVENT_RESERVATION_CANCELLED,
        idempotency_key=f"reservation:{reservation.id}:cancelled",
        subject="Reserva cancelada · AUREA",
        content=_build_email(
            title="Reserva cancelada",
            preheader="Tu reserva ha sido cancelada.",
            rows=_reservation_rows(reservation),
            text_lines=_reservation_text(reservation),
            message="La reserva indicada ha sido cancelada. Este aviso no gestiona automáticamente pagos ni reembolsos.",
            footer="Aviso de reserva enviado por AUREA Obras y Servicios.",
        ),
    )


def queue_deposit_authorized(session: Session, reservation: Reservation, payment: Payment):
    amount = _format_amount(payment.authorized_amount or payment.amount)
    return _queue_customer(
        session, reservation,
        event_type=EVENT_DEPOSIT_AUTHORIZED,
        idempotency_key=f"deposit:{payment.id}:authorized",
        subject="Fianza autorizada · AUREA",
        content=_build_email(
            title="Fianza autorizada",
            preheader="La retención temporal de tu fianza ha sido autorizada.",
            rows=_reservation_rows(reservation, include_deposit=True) + information_row("Importe autorizado", amount),
            text_lines=_reservation_text(reservation, include_deposit=True) + [f"Importe autorizado: {amount}"],
            message="La fianza es una retención temporal asociada al alquiler; no forma parte del cobro inicial del alquiler.",
            footer="Información de fianza enviada por AUREA Obras y Servicios.",
        ),
    )


def queue_deposit_released(session: Session, reservation: Reservation, payment: Payment):
    amount = _format_amount(payment.authorized_amount or payment.amount)
    return _queue_customer(
        session, reservation,
        event_type=EVENT_DEPOSIT_RELEASED,
        idempotency_key=f"deposit:{payment.id}:released",
        subject="Fianza liberada · AUREA",
        content=_build_email(
            title="Fianza liberada",
            preheader="La autorización de fianza ha sido liberada.",
            rows=_reservation_rows(reservation) + information_row("Importe liberado", amount) + information_row("Fecha", _format_datetime(payment.released_at)),
            text_lines=_reservation_text(reservation) + [f"Importe liberado: {amount}", f"Fecha: {_format_datetime(payment.released_at)}"],
            message="AUREA ha solicitado a Stripe la liberación de la retención temporal de la fianza.",
            footer="Información de fianza enviada por AUREA Obras y Servicios.",
        ),
    )


def queue_deposit_captured(session: Session, reservation: Reservation, payment: Payment):
    amount = _format_amount(payment.captured_amount)
    return _queue_customer(
        session, reservation,
        event_type=EVENT_DEPOSIT_CAPTURED,
        idempotency_key=f"deposit:{payment.id}:captured",
        subject="Actualización de fianza · AUREA",
        content=_build_email(
            title="Fianza capturada",
            preheader="Se ha registrado una captura de fianza.",
            rows=_reservation_rows(reservation) + information_row("Importe capturado", amount) + information_row("Fecha", _format_datetime(payment.captured_at)),
            text_lines=_reservation_text(reservation) + [f"Importe capturado: {amount}", f"Fecha: {_format_datetime(payment.captured_at)}"],
            message="Se ha registrado una captura de la fianza asociada al alquiler. Para cualquier aclaración, contacta con AUREA.",
            footer="Información de fianza enviada por AUREA Obras y Servicios.",
        ),
    )


def queue_reservation_delivered(session: Session, reservation: Reservation):
    return _queue_customer(
        session, reservation,
        event_type=EVENT_RESERVATION_DELIVERED,
        idempotency_key=f"reservation:{reservation.id}:in_progress",
        subject="Herramienta entregada · AUREA",
        content=_build_email(
            title="Herramienta entregada",
            preheader="Tu alquiler ya está en curso.",
            rows=_reservation_rows(reservation) + information_row("Entrega", _format_datetime(reservation.delivered_at)),
            text_lines=_reservation_text(reservation) + [f"Entrega: {_format_datetime(reservation.delivered_at)}"],
            message="La entrega física ha quedado registrada y el alquiler está en curso.",
            footer="Aviso operativo enviado por AUREA Obras y Servicios.",
        ),
    )


def queue_reservation_returned(session: Session, reservation: Reservation):
    return _queue_customer(
        session, reservation,
        event_type=EVENT_RESERVATION_RETURNED,
        idempotency_key=f"reservation:{reservation.id}:returned",
        subject="Devolución registrada · AUREA",
        content=_build_email(
            title="Devolución registrada",
            preheader="La devolución física de la herramienta ha quedado registrada.",
            rows=_reservation_rows(reservation) + information_row("Devolución", _format_datetime(reservation.returned_at)),
            text_lines=_reservation_text(reservation) + [f"Devolución: {_format_datetime(reservation.returned_at)}"],
            message="La devolución física ha sido registrada. Si la reserva incluye fianza, su resolución puede quedar pendiente.",
            footer="Aviso operativo enviado por AUREA Obras y Servicios.",
        ),
    )


def queue_reservation_completed(session: Session, reservation: Reservation):
    return _queue_customer(
        session, reservation,
        event_type=EVENT_RESERVATION_COMPLETED,
        idempotency_key=f"reservation:{reservation.id}:completed",
        subject="Alquiler finalizado · AUREA",
        content=_build_email(
            title="Alquiler finalizado",
            preheader="El alquiler ha quedado cerrado.",
            rows=_reservation_rows(reservation),
            text_lines=_reservation_text(reservation),
            message="El alquiler ha quedado finalizado. Gracias por contar con AUREA.",
            footer="Cierre de alquiler enviado por AUREA Obras y Servicios.",
        ),
    )


def queue_financial_alert(session: Session, payment: Payment, alert_type: str):
    reservation = payment.reservation
    return queue_transactional_email(
        session,
        event_type=alert_type,
        idempotency_key=f"payment:{payment.id}:{alert_type}:{payment.provider_event_id or payment.status}",
        recipient=internal_alert_recipient(),
        subject="Revisión financiera requerida · AUREA",
        content=_build_email(
            title="Revisión financiera requerida",
            preheader="Una operación de alquiler requiere intervención administrativa.",
            rows=information_row("Reserva", f"#{reservation.id}") + information_row("Herramienta", _tool_name(reservation)) + information_row("Estado", payment.status),
            text_lines=[f"Reserva: #{reservation.id}", f"Herramienta: {_tool_name(reservation)}", f"Estado: {payment.status}"],
            message="Revisa esta operación desde la administración de AUREA.",
            footer="Alerta interna de AUREA Obras y Servicios.",
        ),
        reservation_id=reservation.id,
    )
