from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func

from app.extensions import db
from app.services.payment_domain import (
    PAYMENT_PROVIDER_PAYPAL,
    PAYMENT_PROVIDER_STRIPE,
    PAYMENT_STATUS_EXPIRED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_REQUIRES_REVIEW,
    PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION,
    PAYMENT_PURPOSE_RENTAL_CHARGE,
    PAYMENT_STATUS_AUTHORIZATION_EXPIRED,
    PAYMENT_STATUS_AUTHORIZATION_FAILED,
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CAPTURED_PARTIALLY,
    PAYMENT_STATUS_PENDING_AUTHORIZATION,
    PAYMENT_STATUS_RELEASED,
)


class Payment(db.Model):
    """A provider-agnostic payment attempt for one rental reservation."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('stripe', 'paypal')", name="ck_payments_provider"
        ),
        CheckConstraint(
            "purpose IN ('rental_charge', 'deposit_authorization')", name="ck_payments_purpose"
        ),
        CheckConstraint(
            "status IN ('pending', 'paid', 'failed', 'expired', 'requires_review', "
            "'pending_authorization', 'authorized', 'released', 'captured_partially', "
            "'captured', 'authorization_failed', 'authorization_expired')",
            name="ck_payments_status",
        ),
        CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
        UniqueConstraint("provider", "external_payment_id", name="uq_payments_provider_external_id"),
        UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        UniqueConstraint("provider", "provider_event_id", name="uq_payments_provider_event_id"),
        Index("ix_payments_reservation_provider_status", "reservation_id", "provider", "status"),
        Index("ix_payments_reservation_purpose_status", "reservation_id", "purpose", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(
        db.Integer, db.ForeignKey("reservations.id", ondelete="RESTRICT"), nullable=False
    )
    provider = db.Column(db.String(32), nullable=False)
    purpose = db.Column(db.String(32), nullable=False, server_default=PAYMENT_PURPOSE_RENTAL_CHARGE)
    external_payment_id = db.Column(db.String(255), nullable=True)
    provider_checkout_id = db.Column(db.String(255), nullable=True)
    provider_charge_id = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(32), nullable=False, server_default=PAYMENT_STATUS_PENDING)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    idempotency_key = db.Column(db.String(64), nullable=False)
    provider_event_id = db.Column(db.String(255), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    authorized_amount = db.Column(db.Numeric(10, 2), nullable=True)
    captured_amount = db.Column(db.Numeric(10, 2), nullable=True)
    authorized_at = db.Column(db.DateTime(timezone=True), nullable=True)
    capture_before = db.Column(db.DateTime(timezone=True), nullable=True)
    released_at = db.Column(db.DateTime(timezone=True), nullable=True)
    captured_at = db.Column(db.DateTime(timezone=True), nullable=True)
    capture_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    reservation = db.relationship("Reservation", back_populates="payments")


class PaymentEvent(db.Model):
    """Provider event receipts used to make multi-stage payment flows idempotent."""

    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_payment_events_provider_event_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False)
    provider = db.Column(db.String(32), nullable=False)
    provider_event_id = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    payment = db.relationship("Payment", backref="events")


__all__ = [
    "Payment",
    "PaymentEvent",
    "PAYMENT_PROVIDER_STRIPE",
    "PAYMENT_PROVIDER_PAYPAL",
    "PAYMENT_STATUS_PENDING",
    "PAYMENT_STATUS_PAID",
    "PAYMENT_STATUS_FAILED",
    "PAYMENT_STATUS_EXPIRED",
    "PAYMENT_STATUS_REQUIRES_REVIEW",
    "PAYMENT_PURPOSE_RENTAL_CHARGE",
    "PAYMENT_PURPOSE_DEPOSIT_AUTHORIZATION",
    "PAYMENT_STATUS_PENDING_AUTHORIZATION",
    "PAYMENT_STATUS_AUTHORIZED",
    "PAYMENT_STATUS_RELEASED",
    "PAYMENT_STATUS_CAPTURED_PARTIALLY",
    "PAYMENT_STATUS_CAPTURED",
    "PAYMENT_STATUS_AUTHORIZATION_FAILED",
    "PAYMENT_STATUS_AUTHORIZATION_EXPIRED",
]
