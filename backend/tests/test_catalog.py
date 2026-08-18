import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "catalog-test-secret"
os.environ["CLOUDINARY_CLOUD_NAME"] = "catalog-test-cloud"

from app import create_app
from app.extensions import db
from app.models import Tool, ToolImage


class CatalogApiTestCase(unittest.TestCase):
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

    def create_tool(self, **overrides):
        values = {
            "name": "Demo tool",
            "category": "Demo",
            "daily_price": Decimal("10.00"),
            "deposit_amount": Decimal("25.00"),
            "pickup_available": True,
            "delivery_available": False,
            "is_published": True,
            "is_available": True,
        }
        values.update(overrides)
        tool = Tool(**values)
        db.session.add(tool)
        db.session.commit()
        return tool

    @staticmethod
    def create_image(tool, storage_key, position):
        image = ToolImage(
            tool_id=tool.id,
            storage_key=storage_key,
            position=position,
        )
        db.session.add(image)
        db.session.commit()
        return image

    def test_empty_catalog_returns_empty_list(self):
        response = self.client.get("/api/tools")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    @patch("app.routes.tools.get_public_image_url")
    def test_published_tool_appears_and_serializes_decimal_as_string(self, public_url):
        public_url.side_effect = lambda storage_key: f"https://images.example/{storage_key}"
        tool = self.create_tool(
            daily_price=Decimal("10.50"),
            deposit_amount=Decimal("99.00"),
            delivery_price_per_km=Decimal("1.25"),
            included_km=10,
            extra_km_price=Decimal("0.50"),
        )

        response = self.client.get("/api/tools")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            [
                {
                    "id": tool.id,
                    "name": "Demo tool",
                    "category": "Demo",
                    "description": None,
                    "daily_price": "10.50",
                    "deposit_amount": "99.00",
                    "pickup_available": True,
                    "delivery_available": False,
                    "delivery_price_per_km": "1.25",
                    "is_available": True,
                    "included_km": 10,
                    "extra_km_price": "0.50",
                    "images": [],
                }
            ],
        )

    @patch("app.routes.tools.get_public_image_url")
    def test_tool_images_are_ordered_and_do_not_expose_storage_key(self, public_url):
        public_url.side_effect = lambda storage_key: f"https://images.example/{storage_key}"
        tool = self.create_tool()
        self.create_image(tool, "aurea/tools/third", 2)
        self.create_image(tool, "aurea/tools/first", 0)
        self.create_image(tool, "aurea/tools/second", 1)

        response = self.client.get("/api/tools")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()[0]["images"],
            [
                {"url": "https://images.example/aurea/tools/first", "position": 0},
                {"url": "https://images.example/aurea/tools/second", "position": 1},
                {"url": "https://images.example/aurea/tools/third", "position": 2},
            ],
        )
        self.assertNotIn("storage_key", response.get_json()[0]["images"][0])

    @patch("app.routes.tools.get_public_image_url")
    def test_detail_returns_the_same_images_contract(self, public_url):
        public_url.return_value = "https://images.example/aurea/tools/example"
        tool = self.create_tool()
        self.create_image(tool, "aurea/tools/example", 0)

        response = self.client.get(f"/api/tools/{tool.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["images"],
            [{"url": "https://images.example/aurea/tools/example", "position": 0}],
        )

    def test_unpublished_tool_is_not_public(self):
        tool = self.create_tool(is_published=False)

        list_response = self.client.get("/api/tools")
        detail_response = self.client.get(f"/api/tools/{tool.id}")

        self.assertEqual(list_response.get_json(), [])
        self.assertEqual(detail_response.status_code, 404)

    @patch("app.routes.tools.get_public_image_url")
    def test_published_unavailable_tool_remains_visible(self, public_url):
        tool = self.create_tool(is_available=False)

        list_response = self.client.get("/api/tools")
        detail_response = self.client.get(f"/api/tools/{tool.id}")

        self.assertFalse(list_response.get_json()[0]["is_available"])
        self.assertFalse(detail_response.get_json()["is_available"])

    def test_missing_tool_returns_not_found(self):
        response = self.client.get("/api/tools/999999")

        self.assertEqual(response.status_code, 404)
