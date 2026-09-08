"""add replaceable rental payment attempt states

Revision ID: i9e0f1a2b3c4
Revises: h8c9d0e1f2a3
Create Date: 2026-09-08 21:30:00.000000
"""

from alembic import op


revision = "i9e0f1a2b3c4"
down_revision = "h8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_payments_status", "payments", type_="check")
    op.create_check_constraint(
        "ck_payments_status",
        "payments",
        "status IN ('pending', 'processing', 'paid', 'failed', 'expired', 'requires_review', 'superseded', "
        "'pending_authorization', 'authorized', 'released', 'captured_partially', "
        "'captured', 'authorization_failed', 'authorization_expired')",
    )


def downgrade():
    op.drop_constraint("ck_payments_status", "payments", type_="check")
    op.create_check_constraint(
        "ck_payments_status",
        "payments",
        "status IN ('pending', 'paid', 'failed', 'expired', 'requires_review', "
        "'pending_authorization', 'authorized', 'released', 'captured_partially', "
        "'captured', 'authorization_failed', 'authorization_expired')",
    )
