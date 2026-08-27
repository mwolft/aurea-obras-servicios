import os
import unittest
from unittest.mock import Mock, patch

from authlib.integrations.base_client.errors import OAuthError
from werkzeug.security import generate_password_hash

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "google-auth-test-secret"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-google-client-secret"
os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost:5000/api/auth/google/callback"

from app import create_app
from app.extensions import db
from app.models import User
from app.services.google_authentication import GoogleIdentityConflictError, GoogleIdentityError, get_or_create_google_user


class GoogleAuthenticationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def identity(**overrides):
        values = {
            "sub": "google-subject-123",
            "email": "google.user@example.com",
            "email_verified": True,
            "name": "Google User",
        }
        values.update(overrides)
        return values

    def test_verified_google_identity_creates_user_without_password(self):
        user = get_or_create_google_user(self.identity(email="GOOGLE.USER@Example.com"))

        self.assertEqual(user.email, "google.user@example.com")
        self.assertEqual(user.google_sub, "google-subject-123")
        self.assertIsNone(user.password_hash)
        self.assertFalse(user.is_admin)
        self.assertEqual(User.query.count(), 1)

    def test_existing_google_subject_logs_in_without_creating_duplicate(self):
        existing_user = User(
            email="existing@example.com",
            name="Existing User",
            google_sub="google-subject-123",
        )
        db.session.add(existing_user)
        db.session.commit()

        user = get_or_create_google_user(self.identity(email="other@example.com"))

        self.assertEqual(user.id, existing_user.id)
        self.assertEqual(User.query.count(), 1)

    def test_existing_google_subject_does_not_depend_on_the_current_email_claim(self):
        existing_user = User(
            email="existing@example.com",
            name="Existing User",
            google_sub="google-subject-123",
        )
        db.session.add(existing_user)
        db.session.commit()

        user = get_or_create_google_user(self.identity(email_verified=False))

        self.assertEqual(user.id, existing_user.id)

    def test_verified_email_links_existing_password_account_without_overwriting_password(self):
        password_hash = generate_password_hash("existing-password")
        existing_user = User(
            email="existing@example.com",
            name="Existing User",
            password_hash=password_hash,
        )
        db.session.add(existing_user)
        db.session.commit()

        user = get_or_create_google_user(
            self.identity(email="EXISTING@example.com", sub="linked-google-subject")
        )

        self.assertEqual(user.id, existing_user.id)
        self.assertEqual(user.google_sub, "linked-google-subject")
        self.assertEqual(user.password_hash, password_hash)
        self.assertEqual(User.query.count(), 1)

    def test_unverified_google_email_is_rejected(self):
        with self.assertRaises(GoogleIdentityError):
            get_or_create_google_user(self.identity(email_verified=False))

        self.assertEqual(User.query.count(), 0)

    def test_google_identity_does_not_duplicate_an_existing_email_account(self):
        first_user = get_or_create_google_user(self.identity())
        second_user = get_or_create_google_user(self.identity())

        self.assertEqual(second_user.id, first_user.id)
        self.assertEqual(User.query.count(), 1)

    def test_email_linked_to_another_google_subject_is_rejected(self):
        db.session.add(
            User(
                email="google.user@example.com",
                name="Existing Google User",
                google_sub="different-google-subject",
            )
        )
        db.session.commit()

        with self.assertRaises(GoogleIdentityConflictError):
            get_or_create_google_user(self.identity())

    @patch("app.routes.auth.get_google_client")
    def test_google_login_starts_authorization_code_flow_with_nonce(self, get_google_client):
        google_client = Mock()
        google_client.authorize_redirect.return_value = "google-redirect"
        get_google_client.return_value = google_client

        response = self.client.get("/api/auth/google")

        self.assertEqual(response.status_code, 200)
        redirect_uri, = google_client.authorize_redirect.call_args.args
        self.assertEqual(redirect_uri, "http://localhost:5000/api/auth/google/callback")
        self.assertTrue(google_client.authorize_redirect.call_args.kwargs["nonce"])

    @patch("app.routes.auth.get_google_client")
    def test_successful_callback_starts_existing_flask_session_without_exposing_tokens(self, get_google_client):
        google_client = Mock()
        google_client.authorize_access_token.return_value = {
            "access_token": "private-access-token",
            "id_token": "private-id-token",
            "userinfo": self.identity(),
        }
        get_google_client.return_value = google_client

        response = self.client.get("/api/auth/google/callback?code=authorization-code&state=state")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost:3000/login")
        self.assertNotIn(b"private-access-token", response.data)
        self.assertNotIn(b"private-id-token", response.data)
        self.assertEqual(self.client.get("/api/auth/me").get_json()["email"], "google.user@example.com")

    @patch("app.routes.auth.get_google_client")
    def test_invalid_oauth_callback_redirects_without_starting_a_session(self, get_google_client):
        google_client = Mock()
        google_client.authorize_access_token.side_effect = OAuthError(error="mismatching_state")
        get_google_client.return_value = google_client

        response = self.client.get("/api/auth/google/callback?code=authorization-code&state=invalid")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost:3000/login?auth_error=google")
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
