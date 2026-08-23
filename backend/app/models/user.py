from sqlalchemy import UniqueConstraint, func

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("google_sub", name="uq_users_google_sub"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(320), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(512), nullable=True)
    google_sub = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    reservations = db.relationship("Reservation", back_populates="user")
