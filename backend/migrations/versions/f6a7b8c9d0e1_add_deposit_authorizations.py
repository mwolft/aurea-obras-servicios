"""add deposit authorization snapshots and payment lifecycle fields

Revision ID: f6a7b8c9d0e1
Revises: e4f5a6b7c8d9
Create Date: 2026-09-07 21:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade():
    # Existing reservations deliberately remain NULL: inferring historical terms
    # from the tool's current fianza would be contractually incorrect.
    op.add_column("reservations", sa.Column("deposit_amount_snapshot", sa.Numeric(10, 2), nullable=True))
    op.add_column("payments", sa.Column("purpose", sa.String(length=32), server_default="rental_charge", nullable=False))
    op.add_column("payments", sa.Column("provider_checkout_id", sa.String(length=255), nullable=True))
    op.add_column("payments", sa.Column("provider_charge_id", sa.String(length=255), nullable=True))
    op.add_column("payments", sa.Column("authorized_amount", sa.Numeric(10, 2), nullable=True))
    op.add_column("payments", sa.Column("captured_amount", sa.Numeric(10, 2), nullable=True))
    op.add_column("payments", sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("capture_before", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("capture_reason", sa.Text(), nullable=True))
    op.drop_constraint("ck_payments_status", "payments", type_="check")
    op.create_check_constraint("ck_payments_purpose", "payments", "purpose IN ('rental_charge', 'deposit_authorization')")
    op.create_check_constraint(
        "ck_payments_status",
        "payments",
        "status IN ('pending', 'paid', 'failed', 'expired', 'requires_review', "
        "'pending_authorization', 'authorized', 'released', 'captured_partially', "
        "'captured', 'authorization_failed', 'authorization_expired')",
    )
    op.create_index("ix_payments_reservation_purpose_status", "payments", ["reservation_id", "purpose", "status"], unique=False)
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_payment_events_provider_event_id"),
    )


def downgrade():
    op.drop_table("payment_events")
    op.drop_index("ix_payments_reservation_purpose_status", table_name="payments")
    op.drop_constraint("ck_payments_status", "payments", type_="check")
    op.drop_constraint("ck_payments_purpose", "payments", type_="check")
    op.create_check_constraint("ck_payments_status", "payments", "status IN ('pending', 'paid', 'failed', 'expired', 'requires_review')")
    for column in ("capture_reason", "captured_at", "released_at", "capture_before", "authorized_at", "captured_amount", "authorized_amount", "provider_charge_id", "provider_checkout_id", "purpose"):
        op.drop_column("payments", column)
    op.drop_column("reservations", "deposit_amount_snapshot")
