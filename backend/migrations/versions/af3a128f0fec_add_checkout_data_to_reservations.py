"""add checkout data to reservations

Revision ID: af3a128f0fec
Revises: 762ecf436cef
Create Date: 2026-08-20 22:25:36.358840

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af3a128f0fec'
down_revision = '762ecf436cef'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('reservations', sa.Column('customer_name', sa.String(length=255), nullable=True))
    op.add_column('reservations', sa.Column('customer_email', sa.String(length=320), nullable=True))
    op.add_column('reservations', sa.Column('customer_phone', sa.String(length=50), nullable=True))
    op.add_column('reservations', sa.Column('terms_accepted', sa.Boolean(), nullable=True))
    op.add_column('reservations', sa.Column('privacy_accepted', sa.Boolean(), nullable=True))
    op.add_column('reservations', sa.Column('payment_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE reservations SET status = 'confirmed' WHERE status = 'active'"))
    op.alter_column(
        'reservations',
        'status',
        existing_type=sa.String(length=32),
        server_default='pending_payment',
    )
    op.create_check_constraint(
        'ck_reservations_pending_payment_checkout_data',
        'reservations',
        "status != 'pending_payment' OR "
        "(customer_name IS NOT NULL AND customer_email IS NOT NULL AND "
        "customer_phone IS NOT NULL AND terms_accepted IS TRUE AND "
        "privacy_accepted IS TRUE AND payment_expires_at IS NOT NULL)",
    )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE reservations SET status = 'active' "
            "WHERE status IN ('pending_payment', 'confirmed')"
        )
    )
    op.drop_constraint('ck_reservations_pending_payment_checkout_data', 'reservations', type_='check')
    op.alter_column(
        'reservations',
        'status',
        existing_type=sa.String(length=32),
        server_default='active',
    )
    op.drop_column('reservations', 'payment_expires_at')
    op.drop_column('reservations', 'privacy_accepted')
    op.drop_column('reservations', 'terms_accepted')
    op.drop_column('reservations', 'customer_phone')
    op.drop_column('reservations', 'customer_email')
    op.drop_column('reservations', 'customer_name')
