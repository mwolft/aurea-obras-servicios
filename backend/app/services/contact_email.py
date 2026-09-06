"""Compatibility imports for the contact email service.

New email types should live under :mod:`app.services.email` so they share the
same AUREA rendering base.
"""

from app.services.email.contact import (
    ContactEmailConfigurationError,
    ContactEmailDeliveryError,
    build_contact_email,
    build_contact_html,
    build_contact_subject,
    build_contact_text,
    send_contact_email,
)

__all__ = [
    "ContactEmailConfigurationError",
    "ContactEmailDeliveryError",
    "build_contact_email",
    "build_contact_html",
    "build_contact_subject",
    "build_contact_text",
    "send_contact_email",
]
