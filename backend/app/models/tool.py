from sqlalchemy import CheckConstraint, UniqueConstraint, false, func, true

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
