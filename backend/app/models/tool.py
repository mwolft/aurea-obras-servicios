from sqlalchemy import CheckConstraint, Index, UniqueConstraint, false, func, true

from app.extensions import db


class Tool(db.Model):
    __tablename__ = "tools"
    __table_args__ = (
        CheckConstraint("daily_price >= 0", name="ck_tools_daily_price_non_negative"),
        CheckConstraint("deposit_amount >= 0", name="ck_tools_deposit_amount_non_negative"),
        CheckConstraint(
            "delivery_price_per_km >= 0",
            name="ck_tools_delivery_price_per_km_non_negative",
        ),
        CheckConstraint("included_km >= 0", name="ck_tools_included_km_non_negative"),
        CheckConstraint("extra_km_price >= 0", name="ck_tools_extra_km_price_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    daily_price = db.Column(db.Numeric(10, 2), nullable=False)
    deposit_amount = db.Column(db.Numeric(10, 2), nullable=False)
    pickup_available = db.Column(db.Boolean, nullable=False, server_default=true())
    delivery_available = db.Column(db.Boolean, nullable=False, server_default=false())
    delivery_price_per_km = db.Column(db.Numeric(10, 2), nullable=True)
    is_published = db.Column(db.Boolean, nullable=False, server_default=false())
    is_available = db.Column(db.Boolean, nullable=False, server_default=true())
    included_km = db.Column(db.Integer, nullable=True)
    extra_km_price = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    images = db.relationship("ToolImage", back_populates="tool", order_by="ToolImage.position")
    reservations = db.relationship("Reservation", back_populates="tool")
    blocks = db.relationship("ToolBlock", back_populates="tool")

    def __str__(self) -> str:
        """Use the human-readable tool name in administrative relationships."""
        return self.name


class ToolImage(db.Model):
    __tablename__ = "tool_images"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_tool_images_position_non_negative"),
        UniqueConstraint("tool_id", "position", name="uq_tool_images_tool_id_position"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tool_id = db.Column(db.Integer, db.ForeignKey("tools.id", ondelete="RESTRICT"), nullable=False)
    storage_key = db.Column(db.String(512), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    tool = db.relationship("Tool", back_populates="images")


class Reservation(db.Model):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_reservations_date_range"),
        CheckConstraint(
            "status != 'pending_payment' OR "
            "(customer_name IS NOT NULL AND customer_email IS NOT NULL AND "
            "customer_phone IS NOT NULL AND terms_accepted IS TRUE AND "
            "privacy_accepted IS TRUE AND payment_expires_at IS NOT NULL)",
            name="ck_reservations_pending_payment_checkout_data",
        ),
        CheckConstraint(
            "fulfillment_method IS NULL OR fulfillment_method IN ('pickup', 'delivery')",
            name="ck_reservations_fulfillment_method",
        ),
        CheckConstraint("billable_km IS NULL OR billable_km >= 0", name="ck_reservations_billable_km_non_negative"),
        CheckConstraint(
            "daily_price_snapshot IS NULL OR daily_price_snapshot >= 0",
            name="ck_reservations_daily_price_snapshot_non_negative",
        ),
        CheckConstraint(
            "delivery_price_per_km_snapshot IS NULL OR delivery_price_per_km_snapshot >= 0",
            name="ck_reservations_delivery_price_snapshot_non_negative",
        ),
        CheckConstraint("charged_days IS NULL OR charged_days >= 1", name="ck_reservations_charged_days_positive"),
        CheckConstraint("rental_amount IS NULL OR rental_amount >= 0", name="ck_reservations_rental_amount_non_negative"),
        CheckConstraint("delivery_amount IS NULL OR delivery_amount >= 0", name="ck_reservations_delivery_amount_non_negative"),
        CheckConstraint("total_amount IS NULL OR total_amount >= 0", name="ck_reservations_total_amount_non_negative"),
        Index("ix_reservations_tool_status_dates", "tool_id", "status", "start_date", "end_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    tool_id = db.Column(db.Integer, db.ForeignKey("tools.id", ondelete="RESTRICT"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(32), nullable=False, server_default="pending_payment")
    customer_name = db.Column(db.String(255), nullable=True)
    customer_email = db.Column(db.String(320), nullable=True)
    customer_phone = db.Column(db.String(50), nullable=True)
    terms_accepted = db.Column(db.Boolean, nullable=True)
    privacy_accepted = db.Column(db.Boolean, nullable=True)
    payment_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    fulfillment_method = db.Column(db.String(16), nullable=True)
    delivery_address = db.Column(db.Text, nullable=True)
    billable_km = db.Column(db.Numeric(10, 2), nullable=True)
    daily_price_snapshot = db.Column(db.Numeric(10, 2), nullable=True)
    delivery_price_per_km_snapshot = db.Column(db.Numeric(10, 2), nullable=True)
    charged_days = db.Column(db.Integer, nullable=True)
    rental_amount = db.Column(db.Numeric(10, 2), nullable=True)
    delivery_amount = db.Column(db.Numeric(10, 2), nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tool = db.relationship("Tool", back_populates="reservations")
    user = db.relationship("User", back_populates="reservations")


class ToolBlock(db.Model):
    """An operational, all-day block that makes a tool unavailable."""

    __tablename__ = "tool_blocks"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_tool_blocks_date_range"),
        CheckConstraint("length(trim(reason)) > 0", name="ck_tool_blocks_reason_not_blank"),
        Index("ix_tool_blocks_tool_dates", "tool_id", "start_date", "end_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tool_id = db.Column(db.Integer, db.ForeignKey("tools.id", ondelete="RESTRICT"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tool = db.relationship("Tool", back_populates="blocks")
