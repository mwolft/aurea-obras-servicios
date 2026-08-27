import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "admin-cli-test-secret"

from app import create_app
from app.extensions import db
from app.models import User


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
