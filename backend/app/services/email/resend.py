"""Small, shared Resend HTTP transport used by AUREA transactional emails."""

from typing import Any

import requests
from flask import current_app


RESEND_EMAILS_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT_SECONDS = 10


class ResendConfigurationError(RuntimeError):
    """Raised when the shared Resend configuration is incomplete."""


class ResendDeliveryError(RuntimeError):
    """Raised when Resend cannot accept a transactional message."""


def _resend_configuration() -> tuple[str, str]:
    api_key = current_app.config.get("RESEND_API_KEY")
    from_email = current_app.config.get("CONTACT_FROM_EMAIL")
    if not api_key or not from_email:
        raise ResendConfigurationError("Resend email configuration is incomplete.")
    return api_key, from_email


def send_resend_email(
    *,
    recipient: str,
    subject: str,
    text: str,
    html: str,
    reply_to: str | None = None,
) -> str | None:
    """Submit an already rendered email without exposing provider details.

    The returned Resend message id is only for the persistent outbox; callers
    must not expose it to browsers or include it in customer emails.
    """

    api_key, from_email = _resend_configuration()
    payload: dict[str, Any] = {
        "from": from_email,
        "to": [recipient],
        "subject": subject,
        "text": text,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    try:
        response = requests.post(
            RESEND_EMAILS_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=RESEND_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise ResendDeliveryError("Resend did not accept the transactional email.") from error

    try:
        response_body = response.json()
    except ValueError:
        # A successful HTTP response is still an accepted message even if a
        # proxy/provider response has no parsable optional message id.
        return None

    message_id = response_body.get("id") if isinstance(response_body, dict) else None
    return message_id if isinstance(message_id, str) else None
