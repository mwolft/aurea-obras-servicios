import re

from flask import Blueprint, current_app, jsonify, request

from app.services.contact_email import (
    ContactEmailConfigurationError,
    ContactEmailDeliveryError,
    send_contact_email,
)


contact_bp = Blueprint("contact", __name__)

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
SUCCESS_RESPONSE = {"success": True, "message": "Mensaje enviado correctamente."}
DELIVERY_ERROR_RESPONSE = {
    "success": False,
    "message": "No se ha podido enviar el mensaje. Inténtalo de nuevo más tarde.",
}


def validation_error(message: str):
    return jsonify({"success": False, "error": message}), 400


def parse_required_text(
    value: object, field_name: str, *, minimum_length: int, maximum_length: int
) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return None, f"{field_name} es obligatorio."

    normalized_value = value.strip()
    if len(normalized_value) < minimum_length:
        return None, f"{field_name} debe tener al menos {minimum_length} caracteres."

    if len(normalized_value) > maximum_length:
        return None, f"{field_name} no puede superar {maximum_length} caracteres."

    return normalized_value, None


def parse_optional_text(
    value: object, field_name: str, *, maximum_length: int
) -> tuple[str | None, str | None]:
    if value is None:
        return None, None

    if not isinstance(value, str):
        return None, f"{field_name} debe ser texto."

    normalized_value = value.strip()
    if not normalized_value:
        return None, None

    if len(normalized_value) > maximum_length:
        return None, f"{field_name} no puede superar {maximum_length} caracteres."

    return normalized_value, None


def parse_email(value: object) -> tuple[str | None, str | None]:
    email, error = parse_required_text(value, "email", minimum_length=3, maximum_length=254)
    if error:
        return None, error

    normalized_email = email.lower()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        return None, "email debe tener un formato válido."

    return normalized_email, None


@contact_bp.post("/contact")
def send_contact_message():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return validation_error("Se requiere un objeto JSON válido.")

    website = payload.get("website", "")
    if not isinstance(website, str):
        return validation_error("website debe ser texto.")

    if website.strip():
        return jsonify(SUCCESS_RESPONSE)

    name, name_error = parse_required_text(
        payload.get("name"), "name", minimum_length=2, maximum_length=120
    )
    if name_error:
        return validation_error(name_error)

    email, email_error = parse_email(payload.get("email"))
    if email_error:
        return validation_error(email_error)

    phone, phone_error = parse_optional_text(payload.get("phone"), "phone", maximum_length=50)
    if phone_error:
        return validation_error(phone_error)

    subject, subject_error = parse_optional_text(
        payload.get("subject"), "subject", maximum_length=160
    )
    if subject_error:
        return validation_error(subject_error)

    message, message_error = parse_required_text(
        payload.get("message"), "message", minimum_length=10, maximum_length=5000
    )
    if message_error:
        return validation_error(message_error)

    if payload.get("privacyAccepted") is not True:
        return validation_error("Debes aceptar la política de privacidad.")

    try:
        send_contact_email(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message,
        )
    except ContactEmailConfigurationError:
        current_app.logger.error("Contact email configuration is incomplete.")
        return jsonify(DELIVERY_ERROR_RESPONSE), 500
    except ContactEmailDeliveryError as error:
        current_app.logger.warning("Contact email delivery failed: %s", error.__class__.__name__)
        return jsonify(DELIVERY_ERROR_RESPONSE), 502

    return jsonify(SUCCESS_RESPONSE)
