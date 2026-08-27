import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "admin-cli-test-secret"

from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import check_password_hash, generate_password_hash


class AdminCliTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.runner = self.app.test_cli_runner()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def create_user(self):
        user = User(name="CLI User", email="cli.user@example.com")
        db.session.add(user)
        db.session.commit()
        return user.id

    def test_make_admin_promotes_existing_user_and_is_idempotent(self):
        user_id = self.create_user()

        first = self.runner.invoke(args=["make-admin", "CLI.USER@EXAMPLE.COM"])
        second = self.runner.invoke(args=["make-admin", "cli.user@example.com"])

        self.assertEqual(first.exit_code, 0)
        self.assertEqual(second.exit_code, 0)
        self.assertTrue(db.session.get(User, user_id).is_admin)

    def test_make_admin_rejects_unknown_user(self):
        result = self.runner.invoke(args=["make-admin", "missing@example.com"])

        self.assertNotEqual(result.exit_code, 0)

    def test_revoke_admin_removes_administrative_access(self):
        user_id = self.create_user()
        self.runner.invoke(args=["make-admin", "cli.user@example.com"])

        result = self.runner.invoke(args=["revoke-admin", "cli.user@example.com"])

        self.assertEqual(result.exit_code, 0)
        self.assertFalse(db.session.get(User, user_id).is_admin)

    def test_set_password_assigns_a_hash_to_a_google_user_without_changing_admin_access(self):
        user_id = self.create_user()
        user = db.session.get(User, user_id)
        user.is_admin = True
        user.google_sub = "google-subject"
        db.session.commit()

        result = self.runner.invoke(
            args=["set-password", "CLI.USER@EXAMPLE.COM"],
            input="secure-password\nsecure-password\n",
        )

        updated_user = db.session.get(User, user_id)
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(updated_user.is_admin)
        self.assertTrue(check_password_hash(updated_user.password_hash, "secure-password"))
        self.assertNotIn("secure-password", updated_user.password_hash)

    def test_set_password_replaces_an_existing_hash_and_rejects_short_passwords(self):
        user_id = self.create_user()
        user = db.session.get(User, user_id)
        user.password_hash = generate_password_hash("previous-password")
        db.session.commit()

        short_password = self.runner.invoke(
            args=["set-password", "cli.user@example.com"],
            input="short\nshort\n",
        )
        self.assertNotEqual(short_password.exit_code, 0)
        self.assertTrue(check_password_hash(db.session.get(User, user_id).password_hash, "previous-password"))

        reset = self.runner.invoke(
            args=["set-password", "cli.user@example.com"],
            input="new-password\nnew-password\n",
        )
        self.assertEqual(reset.exit_code, 0)
        self.assertTrue(check_password_hash(db.session.get(User, user_id).password_hash, "new-password"))

    def test_set_password_rejects_unknown_user(self):
        result = self.runner.invoke(
            args=["set-password", "missing@example.com"],
            input="secure-password\nsecure-password\n",
        )

        self.assertNotEqual(result.exit_code, 0)
