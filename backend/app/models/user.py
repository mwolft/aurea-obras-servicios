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
    is_admin = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    reservations = db.relationship("Reservation", back_populates="user")

    @property
    def account_type(self) -> str:
        """Provide a safe, human-readable account type for administration."""
        if self.google_sub and self.password_hash:
            return "Google y contraseña"
        if self.google_sub:
            return "Google"
        if self.password_hash:
            return "Correo y contraseña"
        return "Sin contraseña"
