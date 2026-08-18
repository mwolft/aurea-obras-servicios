import unittest
from io import BytesIO
from unittest.mock import Mock, patch

from werkzeug.datastructures import FileStorage

from app.services.cloudinary_storage import (
    CloudinaryStorage,
    CloudinaryStorageError,
    InvalidImageError,
)


class CloudinaryStorageTestCase(unittest.TestCase):
    def setUp(self):
        self.uploader = Mock()
        self.config = patch("app.services.cloudinary_storage.cloudinary.config")
        self.mock_config = self.config.start()
        self.storage = CloudinaryStorage("cloud", "key", "secret", uploader=self.uploader)

    def tearDown(self):
        self.config.stop()

    @staticmethod
    def image_file(filename="tool.jpg", content_type="image/jpeg"):
        return FileStorage(BytesIO(b"image-content"), filename=filename, content_type=content_type)

    def test_upload_returns_cloudinary_public_id(self):
        self.uploader.upload.return_value = {"public_id": "aurea/tools/example"}

        storage_key = self.storage.upload_image(self.image_file())

        self.assertEqual(storage_key, "aurea/tools/example")
        self.uploader.upload.assert_called_once()

    def test_upload_rejects_invalid_image_format_before_upload(self):
        with self.assertRaises(InvalidImageError):
            self.storage.upload_image(self.image_file("tool.txt", "text/plain"))

        self.uploader.upload.assert_not_called()

    def test_upload_requires_cloudinary_public_id(self):
        self.uploader.upload.return_value = {}

        with self.assertRaises(CloudinaryStorageError):
            self.storage.upload_image(self.image_file())

    def test_delete_uses_storage_key(self):
        self.storage.delete_image("aurea/tools/example")

        self.uploader.destroy.assert_called_once_with(
            "aurea/tools/example",
            resource_type="image",
            invalidate=True,
        )

    def test_missing_credentials_are_rejected(self):
        with self.assertRaises(CloudinaryStorageError):
            CloudinaryStorage(None, "key", "secret", uploader=self.uploader)

    @patch("app.services.cloudinary_storage.cloudinary.utils.cloudinary_url")
    def test_build_public_image_url_uses_only_cloud_name(self, cloudinary_url):
        from app.services.cloudinary_storage import build_public_image_url

        cloudinary_url.return_value = ("https://images.example/aurea/tools/example", {})

        image_url = build_public_image_url("aurea/tools/example", "demo-cloud")

        self.assertEqual(image_url, "https://images.example/aurea/tools/example")
        cloudinary_url.assert_called_once_with(
            "aurea/tools/example",
            cloud_name="demo-cloud",
            resource_type="image",
            secure=True,
        )
