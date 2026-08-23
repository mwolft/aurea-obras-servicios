import re

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User


EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class GoogleIdentityError(Exception):
    """Raised when Google does not return a usable verified identity."""


class GoogleIdentityConflictError(GoogleIdentityError):
    """Raised when an email is already linked to a different Google account."""


def _normalized_google_email(value: object) -> str:
    if not isinstance(value, str):
        raise GoogleIdentityError

    email = value.strip().lower()
    if not email or len(email) > 320 or not EMAIL_PATTERN.fullmatch(email):
        raise GoogleIdentityError

    return email


def _google_subject(value: object) -> str:
    if not isinstance(value, str):
        raise GoogleIdentityError

    subject = value.strip()
    if not subject or len(subject) > 255:
        raise GoogleIdentityError

    return subject


def _google_name(value: object, email: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()[:255]

    return email


def get_or_create_google_user(userinfo: dict[str, object]) -> User:
    """Find or safely link a local user from a verified Google OIDC identity."""
    google_sub = _google_subject(userinfo.get("sub"))

    user = User.query.filter_by(google_sub=google_sub).one_or_none()
    if user is not None:
        return user

    if userinfo.get("email_verified") is not True:
        raise GoogleIdentityError

    email = _normalized_google_email(userinfo.get("email"))
    name = _google_name(userinfo.get("name"), email)

    user = User.query.filter_by(email=email).one_or_none()
    if user is not None:
        if user.google_sub is not None:
            raise GoogleIdentityConflictError
        user.google_sub = google_sub
    else:
        user = User(
            email=email,
            name=name,
            google_sub=google_sub,
            password_hash=None,
        )
        db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing_user = User.query.filter_by(google_sub=google_sub).one_or_none()
        if existing_user is not None:
            return existing_user
        raise GoogleIdentityConflictError from None

    return user
