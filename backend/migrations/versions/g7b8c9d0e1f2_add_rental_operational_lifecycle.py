"""add physical rental handover and return fields

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-08 08:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reservations", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reservations", sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reservations", sa.Column("delivery_notes", sa.Text(), nullable=True))
    op.add_column("reservations", sa.Column("return_notes", sa.Text(), nullable=True))
    op.add_column("reservations", sa.Column("return_incident_notes", sa.Text(), nullable=True))


def downgrade():
    for column in (
        "return_incident_notes",
        "return_notes",
        "delivery_notes",
        "returned_at",
        "delivered_at",
    ):
        op.drop_column("reservations", column)
