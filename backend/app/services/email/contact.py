"""Contact-specific content and delivery using AUREA's common email shell."""

from flask import current_app
import requests

from .base import EmailContent, information_block, information_row, message_block, render_email


RESEND_EMAILS_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT_SECONDS = 10
CONTACT_EMAIL_TITLE = "Nuevo contacto desde la web"
CONTACT_EMAIL_PREHEADER = "Has recibido una nueva consulta desde la web de AUREA."
CONTACT_EMAIL_FOOTER = "Mensaje recibido desde el formulario web de AUREA."


class ContactEmailConfigurationError(RuntimeError):
    """Raised when contact email delivery has not been configured."""


class ContactEmailDeliveryError(RuntimeError):
    """Raised when Resend cannot accept a contact email."""


def build_contact_subject(subject: str | None) -> str:
    if subject:
        return f"Contacto web AUREA: {subject}"

    return "Nuevo contacto desde la web de AUREA"


def build_contact_text(
    *, name: str, email: str, phone: str | None, subject: str | None, message: str
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
    lines.extend(("", "Mensaje:", message, "", CONTACT_EMAIL_FOOTER))
    return "\n".join(lines)


def build_contact_html(
    *, name: str, email: str, phone: str | None, subject: str | None, message: str
) -> str:
    rows = information_row("Nombre", name) + information_row("Email", email)
    if phone:
        rows += information_row("Teléfono", phone)
    if subject:
        rows += information_row("Asunto", subject)
    return render_email(
        title=CONTACT_EMAIL_TITLE,
        preheader=CONTACT_EMAIL_PREHEADER,
        body_html=information_block(rows) + message_block("Mensaje", message),
        footer_text=CONTACT_EMAIL_FOOTER,
    )


def build_contact_email(
    *, name: str, email: str, phone: str | None, subject: str | None, message: str
) -> EmailContent:
    return EmailContent(
        html=build_contact_html(
            name=name, email=email, phone=phone, subject=subject, message=message
        ),
        text=build_contact_text(
            name=name, email=email, phone=phone, subject=subject, message=message
        ),
    )


def send_contact_email(
    *, name: str, email: str, phone: str | None, subject: str | None, message: str
) -> None:
    api_key = current_app.config.get("RESEND_API_KEY")
    from_email = current_app.config.get("CONTACT_FROM_EMAIL")
    to_email = current_app.config.get("CONTACT_TO_EMAIL")
    if not all((api_key, from_email, to_email)):
        raise ContactEmailConfigurationError("Contact email configuration is incomplete.")
    content = build_contact_email(
        name=name, email=email, phone=phone, subject=subject, message=message
    )
    payload = {
        "from": from_email,
        "to": [to_email],
        "reply_to": email,
        "subject": build_contact_subject(subject),
        "text": content.text,
        "html": content.html,
    }
    try:
        response = requests.post(
            RESEND_EMAILS_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=RESEND_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise ContactEmailDeliveryError("Resend did not accept the contact email.") from error
