import os
import unittest
from unittest.mock import patch

from app import create_app


class AdminAvailabilityTestCase(unittest.TestCase):
    @staticmethod
    def create_test_app(app_env: str):
        with patch.dict(
            os.environ,
            {
                "APP_ENV": app_env,
                "DATABASE_URL": "sqlite:///:memory:",
                "SECRET_KEY": "admin-test-secret",
            },
            clear=False,
        ):
            return create_app()

    def test_admin_is_available_in_development(self):
        response = self.create_test_app("development").test_client().get("/admin/")

        self.assertEqual(response.status_code, 200)

    def test_admin_is_not_registered_in_production(self):
        response = self.create_test_app("production").test_client().get("/admin/")

        self.assertEqual(response.status_code, 404)
