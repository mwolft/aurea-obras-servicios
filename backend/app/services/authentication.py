from flask import session

from app.extensions import db
from app.models import User


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
