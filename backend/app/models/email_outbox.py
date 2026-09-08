"""Persistent transactional-email outbox.

Rows are created together with the business transition that caused them.  The
actual Resend request happens only after that transaction has committed, so a
delivery problem can never roll back a payment or rental operation.
"""

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func

from app.extensions import db


EMAIL_OUTBOX_STATUS_PENDING = "pending"
EMAIL_OUTBOX_STATUS_FAILED = "failed"
EMAIL_OUTBOX_STATUS_SENT = "sent"


class EmailOutbox(db.Model):
    """A rendered transactional email awaiting, or recording, delivery."""

    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'failed', 'sent')",
            name="ck_email_outbox_status",
        ),
        UniqueConstraint("idempotency_key", name="uq_email_outbox_idempotency_key"),
        Index("ix_email_outbox_status_created", "status", "created_at"),
        Index("ix_email_outbox_reservation_event", "reservation_id", "event_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(64), nullable=False)
    reservation_id = db.Column(
        db.Integer,
        db.ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    recipient = db.Column(db.String(320), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    text_body = db.Column(db.Text, nullable=False)
    html_body = db.Column(db.Text, nullable=False)
    idempotency_key = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(16), nullable=False, server_default=EMAIL_OUTBOX_STATUS_PENDING)
    resend_email_id = db.Column(db.String(255), nullable=True)
    last_error = db.Column(db.String(500), nullable=True)
    attempt_count = db.Column(db.Integer, nullable=False, server_default="0")
    last_attempt_at = db.Column(db.DateTime(timezone=True), nullable=True)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    reservation = db.relationship("Reservation", back_populates="email_outbox")

