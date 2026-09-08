"""add persistent transactional email outbox

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-09-08 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "h8c9d0e1f2a3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("resend_email_id", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'failed', 'sent')", name="ck_email_outbox_status"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_email_outbox_idempotency_key"),
    )
    op.create_index("ix_email_outbox_status_created", "email_outbox", ["status", "created_at"], unique=False)
    op.create_index("ix_email_outbox_reservation_event", "email_outbox", ["reservation_id", "event_type"], unique=False)


def downgrade():
    op.drop_index("ix_email_outbox_reservation_event", table_name="email_outbox")
    op.drop_index("ix_email_outbox_status_created", table_name="email_outbox")
    op.drop_table("email_outbox")
