import re

from flask import session
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import User


EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def normalize_email(value: str) -> str:
    """Normalize an email address consistently across authentication flows."""
    return value.strip().lower()


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(value))


def authenticate_with_password(email: str, password: str) -> User | None:
    """Return a user only when its stored password hash matches the password."""
    user = User.query.filter_by(email=normalize_email(email)).first()
    if user is None or user.password_hash is None:
        return None

    return user if check_password_hash(user.password_hash, password) else None


def start_user_session(user: User) -> None:
    """Replace any existing Flask session with a session for the given user."""
    session.clear()
    session["user_id"] = user.id


def get_authenticated_user_id() -> int | None:
    """Return the authenticated id stored in Flask's signed session cookie."""
    user_id = session.get("user_id")

    return user_id if isinstance(user_id, int) and not isinstance(user_id, bool) else None


def get_current_user() -> User | None:
    user_id = get_authenticated_user_id()
    if user_id is None:
        return None

    user = db.session.get(User, user_id)
    if user is None:
        session.pop("user_id", None)

    return user


def serialize_user(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
    }
