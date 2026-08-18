from pathlib import Path

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from flask import current_app
from werkzeug.datastructures import FileStorage


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class CloudinaryStorageError(RuntimeError):
    """Raised when a Cloudinary storage operation cannot be completed."""


class InvalidImageError(ValueError):
    """Raised when an uploaded file is not an allowed image."""


class CloudinaryStorage:
    def __init__(
        self,
        cloud_name: str | None,
        api_key: str | None,
        api_secret: str | None,
        uploader=cloudinary.uploader,
    ):
        if not all((cloud_name, api_key, api_secret)):
            raise CloudinaryStorageError("Cloudinary credentials must be configured.")

        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )
        self.uploader = uploader

    def upload_image(self, image_file: FileStorage) -> str:
        self.validate_image(image_file)
        result = self.uploader.upload(
            image_file.stream,
            resource_type="image",
            folder="aurea/tools",
        )
        storage_key = result.get("public_id")

        if not storage_key:
            raise CloudinaryStorageError("Cloudinary upload did not return a public ID.")

        return storage_key

    def delete_image(self, storage_key: str) -> None:
        self.uploader.destroy(storage_key, resource_type="image", invalidate=True)

    @staticmethod
    def validate_image(image_file: FileStorage | None) -> None:
        if image_file is None or not image_file.filename:
            raise InvalidImageError("An image file is required.")

        extension = Path(image_file.filename).suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise InvalidImageError("Unsupported image file extension.")

        if image_file.mimetype not in ALLOWED_IMAGE_MIME_TYPES:
            raise InvalidImageError("Unsupported image MIME type.")


def get_cloudinary_storage() -> CloudinaryStorage:
    return CloudinaryStorage(
        cloud_name=current_app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=current_app.config["CLOUDINARY_API_KEY"],
        api_secret=current_app.config["CLOUDINARY_API_SECRET"],
    )


def build_public_image_url(storage_key: str, cloud_name: str | None) -> str:
    """Build a public delivery URL without exposing Cloudinary credentials."""
    if not cloud_name:
        raise CloudinaryStorageError("Cloudinary cloud name must be configured.")

    image_url, _ = cloudinary.utils.cloudinary_url(
        storage_key,
        cloud_name=cloud_name,
        resource_type="image",
        secure=True,
    )
    return image_url


def get_public_image_url(storage_key: str) -> str:
    return build_public_image_url(
        storage_key,
        current_app.config["CLOUDINARY_CLOUD_NAME"],
    )
