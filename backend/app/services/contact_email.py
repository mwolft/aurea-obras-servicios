from flask import current_app
import requests


RESEND_EMAILS_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT_SECONDS = 10


class ContactEmailConfigurationError(RuntimeError):
    """Raised when contact email delivery has not been configured."""


class ContactEmailDeliveryError(RuntimeError):
    """Raised when Resend cannot accept a contact email."""


def build_contact_subject(subject: str | None) -> str:
    if subject:
        return f"Contacto web AUREA: {subject}"

    return "Nuevo contacto desde la web de AUREA"


def build_contact_text(
    *,
    name: str,
    email: str,
    phone: str | None,
    subject: str | None,
    message: str,
) -> str:
    lines = [
        "Nuevo mensaje recibido desde el formulario web de AUREA.",
        "",
        f"Nombre: {name}",
        f"Email: {email}",
    ]

    if phone:
        lines.append(f"Teléfono: {phone}")

    if subject:
        lines.append(f"Asunto: {subject}")

    lines.extend(("", "Mensaje:", message))
    return "\n".join(lines)


def send_contact_email(
    *,
    name: str,
    email: str,
    phone: str | None,
    subject: str | None,
    message: str,
) -> None:
    api_key = current_app.config.get("RESEND_API_KEY")
    from_email = current_app.config.get("CONTACT_FROM_EMAIL")
    to_email = current_app.config.get("CONTACT_TO_EMAIL")

    if not all((api_key, from_email, to_email)):
        raise ContactEmailConfigurationError("Contact email configuration is incomplete.")

    payload = {
        "from": from_email,
        "to": [to_email],
        "reply_to": email,
        "subject": build_contact_subject(subject),
        "text": build_contact_text(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message,
        ),
    }

    try:
        response = requests.post(
            RESEND_EMAILS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=RESEND_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise ContactEmailDeliveryError("Resend did not accept the contact email.") from error
