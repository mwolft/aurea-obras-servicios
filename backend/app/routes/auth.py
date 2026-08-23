import re
import secrets

from authlib.integrations.base_client.errors import OAuthError
from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for
from joserfc.errors import JoseError
from requests import RequestException
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, oauth
from app.models import User
from app.services.authentication import get_current_user, serialize_user
from app.services.google_authentication import GoogleIdentityError, get_or_create_google_user


auth_bp = Blueprint("auth", __name__)

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MINIMUM_PASSWORD_LENGTH = 8


def google_is_configured() -> bool:
    return bool(current_app.config["GOOGLE_CLIENT_ID"] and current_app.config["GOOGLE_CLIENT_SECRET"])


def google_login_failed_redirect():
    return redirect(f"{current_app.config['FRONTEND_ORIGIN'].rstrip('/')}/login?auth_error=google")


def google_callback_url() -> str:
    return current_app.config["GOOGLE_REDIRECT_URI"] or url_for("auth.google_callback", _external=True)


def get_google_client():
    return oauth.create_client("google")


def parse_json_object() -> tuple[dict[str, object] | None, tuple[dict[str, str], int] | None]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, ({"error": "A JSON object is required."}, 400)

    return payload, None


def parse_required_text(
    value: object, field_name: str
) -> tuple[str | None, tuple[dict[str, str], int] | None]:
    if not isinstance(value, str) or not value.strip():
        return None, ({"error": f"{field_name} is required."}, 400)

    return value.strip(), None


def parse_email(value: object) -> tuple[str | None, tuple[dict[str, str], int] | None]:
    email, error = parse_required_text(value, "email")
    if error:
        return None, error

    normalized_email = email.lower()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        return None, ({"error": "email must be a valid email address."}, 400)

    return normalized_email, None


def parse_password(value: object) -> tuple[str | None, tuple[dict[str, str], int] | None]:
    if not isinstance(value, str) or len(value) < MINIMUM_PASSWORD_LENGTH:
        return None, (
            {"error": f"password must contain at least {MINIMUM_PASSWORD_LENGTH} characters."},
            400,
        )

    return value, None


@auth_bp.post("/register")
def register():
    payload, payload_error = parse_json_object()
    if payload_error:
        return jsonify(payload_error[0]), payload_error[1]

    name, name_error = parse_required_text(payload.get("name"), "name")
    if name_error:
        return jsonify(name_error[0]), name_error[1]

    email, email_error = parse_email(payload.get("email"))
    if email_error:
        return jsonify(email_error[0]), email_error[1]

    password, password_error = parse_password(payload.get("password"))
    if password_error:
        return jsonify(password_error[0]), password_error[1]

    if User.query.filter_by(email=email).first() is not None:
        return jsonify({"error": "An account with that email already exists."}), 409

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "An account with that email already exists."}), 409

    session.clear()
    session["user_id"] = user.id

    return jsonify(serialize_user(user)), 201


@auth_bp.post("/login")
def login():
    payload, payload_error = parse_json_object()
    if payload_error:
        return jsonify(payload_error[0]), payload_error[1]

    email, email_error = parse_email(payload.get("email"))
    if email_error:
        return jsonify(email_error[0]), email_error[1]

    password, password_error = parse_password(payload.get("password"))
    if password_error:
        return jsonify(password_error[0]), password_error[1]

    user = User.query.filter_by(email=email).first()
    if user is None or user.password_hash is None or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password."}), 401

    session.clear()
    session["user_id"] = user.id

    return jsonify(serialize_user(user))


@auth_bp.post("/logout")
def logout():
    session.clear()

    return jsonify({"status": "ok"})


@auth_bp.get("/google")
def google_login():
    if not google_is_configured():
        return jsonify({"error": "Google login is not configured."}), 503

    return get_google_client().authorize_redirect(
        google_callback_url(),
        nonce=secrets.token_urlsafe(32),
    )


@auth_bp.get("/google/callback")
def google_callback():
    if not google_is_configured():
        return jsonify({"error": "Google login is not configured."}), 503

    if request.args.get("error"):
        return google_login_failed_redirect()

    try:
        token = get_google_client().authorize_access_token()
        userinfo = token.get("userinfo")
        if not isinstance(userinfo, dict):
            raise GoogleIdentityError
        user = get_or_create_google_user(userinfo)
    except (GoogleIdentityError, JoseError, OAuthError, RequestException):
        return google_login_failed_redirect()

    session.clear()
    session["user_id"] = user.id

    return redirect(f"{current_app.config['FRONTEND_ORIGIN'].rstrip('/')}/login")


@auth_bp.get("/me")
def me():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required."}), 401

    return jsonify(serialize_user(user))
