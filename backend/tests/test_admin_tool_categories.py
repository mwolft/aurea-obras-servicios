import os
import re
import unittest
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "admin-tool-categories-test-secret"
os.environ["APP_ENV"] = "development"

from app import create_app
from app.extensions import db
from app.models import Tool, User


class AdminToolCategoryTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

        admin = User(name="Catalog admin", email="catalog-admin@example.com", is_admin=True)
        db.session.add(admin)
        db.session.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = admin.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def csrf_token(self, response):
        token = re.search(
            r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
        )
        self.assertIsNotNone(token)
        return token.group(1)

    def tool_form_data(self, form_page, *, category):
        return {
            "csrf_token": self.csrf_token(form_page),
            "name": "Herramienta de prueba",
            "category": category,
            "description": "Descripción de prueba",
            "daily_price": "10.00",
            "deposit_amount": "25.00",
            "pickup_available": "y",
            "is_published": "y",
            "is_available": "y",
        }

    def create_tool(self, *, category="Maquinaria"):
        tool = Tool(
            name="Herramienta existente",
            category=category,
            daily_price=Decimal("10.00"),
            deposit_amount=Decimal("25.00"),
            pickup_available=True,
            delivery_available=False,
            is_published=True,
            is_available=True,
        )
        db.session.add(tool)
        db.session.commit()
        return tool

    def test_new_tool_form_renders_a_closed_category_select(self):
        response = self.client.get("/admin/tool/new/")
        content = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="category" name="category"', content)
        self.assertIn('data-role="select2"', content)
        self.assertIn('<option value="Maquinaria">Maquinaria</option>', content)
        self.assertIn('<option value="Herramientas">Herramientas</option>', content)
        self.assertNotIn('<input class="form-control" id="category"', content)

    def test_admin_creates_tool_with_a_supported_category(self):
        form_page = self.client.get("/admin/tool/new/")

        response = self.client.post(
            "/admin/tool/new/",
            data=self.tool_form_data(form_page, category="Herramientas"),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Tool.query.one().category, "Herramientas")

    def test_admin_edit_keeps_a_supported_category(self):
        tool = self.create_tool(category="Maquinaria")
        form_page = self.client.get(f"/admin/tool/edit/?id={tool.id}")
        data = self.tool_form_data(form_page, category="Herramientas")
        data["name"] = tool.name

        response = self.client.post(f"/admin/tool/edit/?id={tool.id}", data=data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Tool, tool.id).category, "Herramientas")

    def test_admin_rejects_an_arbitrary_category(self):
        form_page = self.client.get("/admin/tool/new/")

        response = self.client.post(
            "/admin/tool/new/",
            data=self.tool_form_data(form_page, category="Otra categoría"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Opción inválida.", response.get_data(as_text=True))
        self.assertEqual(Tool.query.count(), 0)
