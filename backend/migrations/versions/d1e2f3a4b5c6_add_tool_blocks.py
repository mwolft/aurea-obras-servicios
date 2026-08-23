"""add operational tool blocks

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-08-22 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tool_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_tool_blocks_date_range"),
        sa.CheckConstraint("length(trim(reason)) > 0", name="ck_tool_blocks_reason_not_blank"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_blocks_tool_dates", "tool_blocks", ["tool_id", "start_date", "end_date"])


def downgrade():
    op.drop_index("ix_tool_blocks_tool_dates", table_name="tool_blocks")
    op.drop_table("tool_blocks")
