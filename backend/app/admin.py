import logging

from flask import Flask
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from wtforms import FileField

from app.extensions import db
from app.models import Tool, ToolImage
from app.services.cloudinary_storage import get_cloudinary_storage


logger = logging.getLogger(__name__)


class ToolAdmin(ModelView):
    can_delete = False
    column_list = (
        "name",
        "category",
        "daily_price",
        "deposit_amount",
        "is_published",
        "is_available",
        "delivery_available",
    )
    column_searchable_list = ("name", "category")
    column_filters = ("category", "is_published", "is_available")
    form_columns = (
        "name",
        "category",
        "description",
        "daily_price",
        "deposit_amount",
        "pickup_available",
        "delivery_available",
        "delivery_price_per_km",
        "is_published",
        "is_available",
        "included_km",
        "extra_km_price",
    )


class ToolImageAdmin(ModelView):
    column_list = ("tool", "storage_key", "position", "created_at")
    column_searchable_list = ("storage_key",)
    column_default_sort = ("position", False)
    form_extra_fields = {"image_file": FileField("Archivo de imagen")}
    form_columns = ("tool", "image_file", "position")

    def on_model_change(self, form, model, is_created):
        image_file = form.image_file.data

        if image_file and image_file.filename:
            storage = get_cloudinary_storage()
            previous_storage_key = None if is_created else model.storage_key
            model.storage_key = storage.upload_image(image_file)
            form._uploaded_storage_key = model.storage_key
            form._previous_storage_key = previous_storage_key
        elif is_created:
            raise ValueError("Debe seleccionar un archivo de imagen.")

    def after_model_change(self, form, model, is_created):
        previous_storage_key = getattr(form, "_previous_storage_key", None)

        if previous_storage_key and previous_storage_key != model.storage_key:
            self._delete_asset_safely(previous_storage_key)

    def after_model_delete(self, model):
        self._delete_asset_safely(model.storage_key)

    def create_model(self, form):
        result = super().create_model(form)

        if result is False:
            self._delete_uploaded_asset_safely(form)

        return result

    def update_model(self, form, model):
        result = super().update_model(form, model)

        if not result:
            self._delete_uploaded_asset_safely(form)

        return result

    @staticmethod
    def _delete_asset_safely(storage_key):
        try:
            get_cloudinary_storage().delete_image(storage_key)
        except Exception:
            logger.exception("Cloudinary asset cleanup failed.")

    def _delete_uploaded_asset_safely(self, form):
        storage_key = getattr(form, "_uploaded_storage_key", None)

        if storage_key:
            self._delete_asset_safely(storage_key)


def init_admin(app: Flask) -> Admin:
    admin = Admin(app, name="AUREA Administración", url="/admin")
    admin.add_view(ToolAdmin(Tool, db, category="Catálogo"))
    admin.add_view(ToolImageAdmin(ToolImage, db, category="Catálogo"))

    return admin
