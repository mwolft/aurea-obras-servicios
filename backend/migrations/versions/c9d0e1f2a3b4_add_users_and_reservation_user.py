"""add users and reservation user

Revision ID: c9d0e1f2a3b4
Revises: b4d6e7f8a901
Create Date: 2026-08-21 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9d0e1f2a3b4"
down_revision = "b4d6e7f8a901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=True),
        sa.Column("google_sub", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("google_sub", name="uq_users_google_sub"),
    )
    op.add_column("reservations", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_reservations_user_id_users",
        "reservations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_reservations_user_id", "reservations", ["user_id"], unique=False)


def downgrade():
    op.drop_index("ix_reservations_user_id", table_name="reservations")
    op.drop_constraint("fk_reservations_user_id_users", "reservations", type_="foreignkey")
    op.drop_column("reservations", "user_id")
    op.drop_table("users")
