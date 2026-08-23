"""add reservation quote snapshots

Revision ID: b4d6e7f8a901
Revises: af3a128f0fec
Create Date: 2026-08-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4d6e7f8a901"
down_revision = "af3a128f0fec"
branch_labels = None
depends_on = None


def upgrade():
    # All columns stay nullable so existing confirmed reservations retain their
    # historical data even though they predate quote snapshots.
    op.add_column("reservations", sa.Column("fulfillment_method", sa.String(length=16), nullable=True))
    op.add_column("reservations", sa.Column("delivery_address", sa.Text(), nullable=True))
    op.add_column("reservations", sa.Column("billable_km", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column(
        "reservations", sa.Column("daily_price_snapshot", sa.Numeric(precision=10, scale=2), nullable=True)
    )
    op.add_column(
        "reservations",
        sa.Column("delivery_price_per_km_snapshot", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column("reservations", sa.Column("charged_days", sa.Integer(), nullable=True))
    op.add_column("reservations", sa.Column("rental_amount", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column("reservations", sa.Column("delivery_amount", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column("reservations", sa.Column("total_amount", sa.Numeric(precision=10, scale=2), nullable=True))

    op.create_check_constraint(
        "ck_reservations_fulfillment_method",
        "reservations",
        "fulfillment_method IS NULL OR fulfillment_method IN ('pickup', 'delivery')",
    )
    op.create_check_constraint(
        "ck_reservations_billable_km_non_negative",
        "reservations",
        "billable_km IS NULL OR billable_km >= 0",
    )
    op.create_check_constraint(
        "ck_reservations_daily_price_snapshot_non_negative",
        "reservations",
        "daily_price_snapshot IS NULL OR daily_price_snapshot >= 0",
    )
    op.create_check_constraint(
        "ck_reservations_delivery_price_snapshot_non_negative",
        "reservations",
        "delivery_price_per_km_snapshot IS NULL OR delivery_price_per_km_snapshot >= 0",
    )
    op.create_check_constraint(
        "ck_reservations_charged_days_positive",
        "reservations",
        "charged_days IS NULL OR charged_days >= 1",
    )
    op.create_check_constraint(
        "ck_reservations_rental_amount_non_negative",
        "reservations",
        "rental_amount IS NULL OR rental_amount >= 0",
    )
    op.create_check_constraint(
        "ck_reservations_delivery_amount_non_negative",
        "reservations",
        "delivery_amount IS NULL OR delivery_amount >= 0",
    )
    op.create_check_constraint(
        "ck_reservations_total_amount_non_negative",
        "reservations",
        "total_amount IS NULL OR total_amount >= 0",
    )


def downgrade():
    op.drop_constraint("ck_reservations_total_amount_non_negative", "reservations", type_="check")
    op.drop_constraint("ck_reservations_delivery_amount_non_negative", "reservations", type_="check")
    op.drop_constraint("ck_reservations_rental_amount_non_negative", "reservations", type_="check")
    op.drop_constraint("ck_reservations_charged_days_positive", "reservations", type_="check")
    op.drop_constraint("ck_reservations_delivery_price_snapshot_non_negative", "reservations", type_="check")
    op.drop_constraint("ck_reservations_daily_price_snapshot_non_negative", "reservations", type_="check")
    op.drop_constraint("ck_reservations_billable_km_non_negative", "reservations", type_="check")
    op.drop_constraint("ck_reservations_fulfillment_method", "reservations", type_="check")

    op.drop_column("reservations", "total_amount")
    op.drop_column("reservations", "delivery_amount")
    op.drop_column("reservations", "rental_amount")
    op.drop_column("reservations", "charged_days")
    op.drop_column("reservations", "delivery_price_per_km_snapshot")
    op.drop_column("reservations", "daily_price_snapshot")
    op.drop_column("reservations", "billable_km")
    op.drop_column("reservations", "delivery_address")
    op.drop_column("reservations", "fulfillment_method")
