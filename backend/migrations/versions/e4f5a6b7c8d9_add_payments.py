"""add provider-agnostic payment attempts

Revision ID: e4f5a6b7c8d9
Revises: daf3106ac4a5
Create Date: 2026-09-07 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e4f5a6b7c8d9"
down_revision = "daf3106ac4a5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_payment_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("provider IN ('stripe', 'paypal')", name="ck_payments_provider"),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'failed', 'expired', 'requires_review')",
            name="ck_payments_status",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_payment_id", name="uq_payments_provider_external_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_payments_provider_event_id"),
    )
    op.create_index(
        "ix_payments_reservation_provider_status",
        "payments",
        ["reservation_id", "provider", "status"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_payments_reservation_provider_status", table_name="payments")
    op.drop_table("payments")
