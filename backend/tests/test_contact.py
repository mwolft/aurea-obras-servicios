import json
import os
import unittest
from unittest.mock import Mock, patch

import requests

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "contact-test-secret"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"
os.environ["RESEND_API_KEY"] = "test-resend-secret"
os.environ["CONTACT_FROM_EMAIL"] = "AUREA <contact@example.test>"
os.environ["CONTACT_TO_EMAIL"] = "inbox@example.test"

from app import create_app


class ContactApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    @staticmethod
    def payload(**overrides):
        values = {
            "name": "Aurea Contact",
            "email": "CONTACT@Example.COM",
            "phone": "600 000 000",
            "subject": "Consulta de jardinería",
            "message": "Necesito información para una parcela.",
            "privacyAccepted": True,
            "website": "",
        }
        values.update(overrides)
        return values

    @patch("app.services.contact_email.requests.post")
    def test_valid_payload_requests_email_delivery(self, post):
        response = self.client.post("/api/contact", json=self.payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(), {"success": True, "message": "Mensaje enviado correctamente."}
        )
        post.assert_called_once()
        request_kwargs = post.call_args.kwargs
        self.assertEqual(request_kwargs["timeout"], 10)
        self.assertEqual(request_kwargs["json"]["from"], "AUREA <contact@example.test>")
        self.assertEqual(request_kwargs["json"]["to"], ["inbox@example.test"])
        self.assertEqual(request_kwargs["json"]["reply_to"], "contact@example.com")
        self.assertEqual(request_kwargs["json"]["subject"], "Contacto web AUREA: Consulta de jardinería")
        self.assertIn("Nombre: Aurea Contact", request_kwargs["json"]["text"])
        self.assertIn("Teléfono: 600 000 000", request_kwargs["json"]["text"])
        self.assertIn("Mensaje:\nNecesito información para una parcela.", request_kwargs["json"]["text"])

    @patch("app.services.contact_email.requests.post")
    def test_optional_fields_are_omitted_from_email_when_blank(self, post):
        response = self.client.post("/api/contact", json=self.payload(phone="", subject=""))

        self.assertEqual(response.status_code, 200)
        request_json = post.call_args.kwargs["json"]
        self.assertEqual(request_json["subject"], "Nuevo contacto desde la web de AUREA")
        self.assertNotIn("Teléfono:", request_json["text"])
        self.assertNotIn("Asunto:", request_json["text"])

    def test_missing_name_is_rejected(self):
        response = self.client.post("/api/contact", json=self.payload(name=""))

        self.assertEqual(response.status_code, 400)

    def test_invalid_email_is_rejected(self):
        response = self.client.post("/api/contact", json=self.payload(email="not-an-email"))

        self.assertEqual(response.status_code, 400)

    def test_missing_message_is_rejected(self):
        response = self.client.post("/api/contact", json=self.payload(message=""))

        self.assertEqual(response.status_code, 400)

    def test_privacy_acceptance_is_required(self):
        response = self.client.post("/api/contact", json=self.payload(privacyAccepted=False))

        self.assertEqual(response.status_code, 400)

    def test_json_and_field_types_are_validated(self):
        self.assertEqual(self.client.post("/api/contact", data="not-json").status_code, 400)
        self.assertEqual(self.client.post("/api/contact", json=self.payload(name=[])).status_code, 400)
        self.assertEqual(self.client.post("/api/contact", json=self.payload(phone=7)).status_code, 400)
        self.assertEqual(self.client.post("/api/contact", json=self.payload(website=[])).status_code, 400)

    @patch("app.services.contact_email.requests.post")
    def test_honeypot_returns_generic_success_without_sending_email(self, post):
        response = self.client.post("/api/contact", json=self.payload(website="https://spam.example"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True, "message": "Mensaje enviado correctamente."})
        post.assert_not_called()

    @patch("app.services.contact_email.requests.post", side_effect=requests.Timeout)
    def test_resend_timeout_returns_generic_provider_error(self, post):
        response = self.client.post("/api/contact", json=self.payload())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["success"], False)
        post.assert_called_once()

    @patch("app.services.contact_email.requests.post")
    def test_resend_http_error_returns_generic_provider_error(self, post):
        resend_response = Mock()
        resend_response.raise_for_status.side_effect = requests.HTTPError("provider error")
        post.return_value = resend_response

        response = self.client.post("/api/contact", json=self.payload())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["success"], False)

    @patch("app.services.contact_email.requests.post")
    def test_missing_configuration_returns_generic_error_without_sending_email(self, post):
        self.app.config["RESEND_API_KEY"] = None

        response = self.client.post("/api/contact", json=self.payload())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["success"], False)
        post.assert_not_called()

    @patch("app.services.contact_email.requests.post")
    def test_responses_do_not_expose_secret_configuration(self, post):
        response = self.client.post("/api/contact", json=self.payload())

        self.assertNotIn("test-resend-secret", json.dumps(response.get_json()))
        self.assertNotIn("contact@example.test", json.dumps(response.get_json()))


if __name__ == "__main__":
    unittest.main()
