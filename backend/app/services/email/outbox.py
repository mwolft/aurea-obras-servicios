"""Queue and deliver transactional emails after their business transaction."""

import logging
from datetime import datetime, timezone
from typing import Iterable

from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models.email_outbox import (
    EMAIL_OUTBOX_STATUS_FAILED,
    EMAIL_OUTBOX_STATUS_PENDING,
    EMAIL_OUTBOX_STATUS_SENT,
    EmailOutbox,
)

from .base import EmailContent
from .resend import ResendConfigurationError, ResendDeliveryError, send_resend_email


logger = logging.getLogger(__name__)


def queue_transactional_email(
    session: Session,
    *,
    event_type: str,
    idempotency_key: str,
    recipient: str | None,
    subject: str,
    content: EmailContent,
    reservation_id: int | None = None,
) -> EmailOutbox | None:
    """Persist one rendered email, or return the row created previously.

    Missing customer/contact configuration is logged and deliberately skipped:
    it must never make an otherwise valid rental transition fail.
    """

    normalized_recipient = recipient.strip() if isinstance(recipient, str) else ""
    if not normalized_recipient:
        logger.warning("Transactional email %s was skipped because no recipient is available.", event_type)
        return None

    existing = session.execute(
        select(EmailOutbox).where(EmailOutbox.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    email = EmailOutbox(
        event_type=event_type,
        reservation_id=reservation_id,
        recipient=normalized_recipient,
        subject=subject,
        text_body=content.text,
        html_body=content.html,
        idempotency_key=idempotency_key,
        status=EMAIL_OUTBOX_STATUS_PENDING,
    )
    session.add(email)
    session.flush()
    return email


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def deliver_outbox_email(email_id: int) -> bool:
    """Attempt a stored email after commit; failures remain retryable.

    A request to Resend is intentionally outside the state-changing rental
    transaction.  This prevents any mail outage from undoing financial or
    operational work.
    """

    # Admin rendering and ORM attribute access can leave a scoped read
    # transaction open after the business transition has already committed.
    # Delivery is explicitly post-commit, so clearing that read transaction is
    # safe and keeps the external side effect isolated.
    db.session.rollback()
    with db.session.begin():
        email = db.session.execute(
            select(EmailOutbox).where(EmailOutbox.id == email_id).with_for_update()
        ).scalar_one_or_none()
        if email is None or email.status == EMAIL_OUTBOX_STATUS_SENT:
            return email is not None
        email.attempt_count = int(email.attempt_count or 0) + 1
        email.last_attempt_at = _utc_now()
        email.last_error = None
        payload = (email.recipient, email.subject, email.text_body, email.html_body)

    try:
        resend_email_id = send_resend_email(
            recipient=payload[0], subject=payload[1], text=payload[2], html=payload[3]
        )
    except (ResendConfigurationError, ResendDeliveryError) as error:
        with db.session.begin():
            email = db.session.execute(
                select(EmailOutbox).where(EmailOutbox.id == email_id).with_for_update()
            ).scalar_one_or_none()
            if email is not None and email.status != EMAIL_OUTBOX_STATUS_SENT:
                email.status = EMAIL_OUTBOX_STATUS_FAILED
                # The class is enough to diagnose delivery without storing a
                # provider response or configuration detail.
                email.last_error = error.__class__.__name__
        logger.warning("Transactional email delivery failed for outbox id %s.", email_id)
        return False
    except Exception as error:  # pragma: no cover - defensive provider boundary.
        with db.session.begin():
            email = db.session.execute(
                select(EmailOutbox).where(EmailOutbox.id == email_id).with_for_update()
            ).scalar_one_or_none()
            if email is not None and email.status != EMAIL_OUTBOX_STATUS_SENT:
                email.status = EMAIL_OUTBOX_STATUS_FAILED
                email.last_error = error.__class__.__name__
        logger.exception("Unexpected transactional email failure for outbox id %s.", email_id)
        return False

    with db.session.begin():
        email = db.session.execute(
            select(EmailOutbox).where(EmailOutbox.id == email_id).with_for_update()
        ).scalar_one_or_none()
        if email is None:
            return False
        email.status = EMAIL_OUTBOX_STATUS_SENT
        email.resend_email_id = resend_email_id
        email.sent_at = _utc_now()
        email.last_error = None
    return True


def deliver_outbox_emails(email_ids: Iterable[int]) -> None:
    """Best-effort delivery for just-committed messages from one operation."""

    for email_id in dict.fromkeys(email_ids):
        try:
            deliver_outbox_email(email_id)
        except Exception:  # pragma: no cover - final safety barrier for webhooks/admin.
            logger.exception("Unexpected transactional email failure for outbox id %s.", email_id)


def retry_failed_outbox_email(email_id: int) -> bool:
    """Manually retry a failed email; sent messages are never re-sent."""

    email = db.session.get(EmailOutbox, email_id)
    if email is None:
        db.session.rollback()
        raise LookupError("No existe el email transaccional solicitado.")
    if email.status == EMAIL_OUTBOX_STATUS_SENT:
        db.session.rollback()
        return False
    if email.status != EMAIL_OUTBOX_STATUS_FAILED:
        db.session.rollback()
        raise ValueError("Solo se pueden reintentar emails fallidos.")
    db.session.rollback()
    return deliver_outbox_email(email_id)


def internal_alert_recipient() -> str | None:
    """Use the existing contact inbox for the small set of internal alerts."""

    value = current_app.config.get("CONTACT_TO_EMAIL")
    return value if isinstance(value, str) and value.strip() else None
