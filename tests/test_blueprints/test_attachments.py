"""Tests for the attachments blueprint."""

import io
import os

import pytest

from app.models.attachment import Attachment
from tests.factories import AttachmentFactory, UserFactory

pytestmark = pytest.mark.blueprint


def _make_file_data(filename="test.jpg", content=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
                    content_type="image/jpeg"):
    """Create a tuple suitable for test client file upload."""
    return (io.BytesIO(content), filename)


class TestUploadEndpoint:
    """Test POST /attachments/upload."""

    def test_upload_valid_image(self, logged_in_client, app):
        """Test uploading a valid image returns 201 with attachment details."""
        data = {
            "file": _make_file_data("photo.jpg"),
            "attachable_type": "service_item",
            "attachable_id": "1",
            "description": "Test photo",
        }
        resp = logged_in_client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        json_data = resp.get_json()
        assert "id" in json_data
        assert json_data["filename"] == "photo.jpg"
        assert "url" in json_data
        assert json_data["is_image"] is True

        # Cleanup file
        att = Attachment.query.get(json_data["id"])
        if att:
            from app.services import attachment_service
            path = attachment_service.get_attachment_path(att)
            if os.path.exists(path):
                os.remove(path)

    def test_upload_requires_authentication(self, client):
        """Test that upload requires login."""
        data = {
            "file": _make_file_data(),
            "attachable_type": "service_item",
            "attachable_id": "1",
        }
        resp = client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        # Should redirect to login
        assert resp.status_code in (302, 401)

    def test_upload_requires_admin_or_tech_role(self, viewer_client):
        """Test that viewer role cannot upload."""
        data = {
            "file": _make_file_data(),
            "attachable_type": "service_item",
            "attachable_id": "1",
        }
        resp = viewer_client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 403

    def test_upload_invalid_file_type(self, logged_in_client):
        """Test that uploading a disallowed file type returns 400."""
        data = {
            "file": _make_file_data("bad.exe"),
            "attachable_type": "service_item",
            "attachable_id": "1",
        }
        resp = logged_in_client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_upload_invalid_attachable_type(self, logged_in_client):
        """Test that invalid attachable_type returns 400."""
        data = {
            "file": _make_file_data(),
            "attachable_type": "invalid_type",
            "attachable_id": "1",
        }
        resp = logged_in_client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.get_json()["error"]

    def test_upload_missing_file(self, logged_in_client):
        """Test that missing file returns 400."""
        data = {
            "attachable_type": "service_item",
            "attachable_id": "1",
        }
        resp = logged_in_client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_missing_attachable_id(self, logged_in_client):
        """Test that missing attachable_id returns 400."""
        data = {
            "file": _make_file_data(),
            "attachable_type": "service_item",
        }
        resp = logged_in_client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


class TestServeFileEndpoint:
    """Test GET /attachments/<id>/file."""

    def test_serve_existing_file(self, logged_in_client, app, db_session):
        """Test serving an existing attachment file."""
        # First upload a file
        data = {
            "file": _make_file_data("serve_test.jpg"),
            "attachable_type": "service_item",
            "attachable_id": "1",
        }
        upload_resp = logged_in_client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        att_id = upload_resp.get_json()["id"]

        # Serve it
        resp = logged_in_client.get(f"/attachments/{att_id}/file")
        assert resp.status_code == 200
        assert resp.content_type.startswith("image/jpeg")

        # Cleanup
        att = Attachment.query.get(att_id)
        if att:
            from app.services import attachment_service
            path = attachment_service.get_attachment_path(att)
            if os.path.exists(path):
                os.remove(path)

    def test_serve_nonexistent_returns_404(self, logged_in_client):
        """Test that requesting a nonexistent attachment returns 404."""
        resp = logged_in_client.get("/attachments/99999/file")
        assert resp.status_code == 404

    def test_serve_requires_login(self, client):
        """Test that file serving requires authentication."""
        resp = client.get("/attachments/1/file")
        assert resp.status_code in (302, 401)


class TestThumbnailEndpoint:
    """Test GET /attachments/<id>/thumbnail."""

    def test_thumbnail_nonexistent_returns_404(self, logged_in_client):
        """Test that thumbnail for nonexistent attachment returns 404."""
        resp = logged_in_client.get("/attachments/99999/thumbnail")
        assert resp.status_code == 404

    def test_thumbnail_returns_image(self, logged_in_client, app, db_session):
        """Test that thumbnail endpoint returns an image."""
        # Upload first
        data = {
            "file": _make_file_data("thumb_test.jpg"),
            "attachable_type": "service_item",
            "attachable_id": "1",
        }
        upload_resp = logged_in_client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        att_id = upload_resp.get_json()["id"]

        resp = logged_in_client.get(f"/attachments/{att_id}/thumbnail")
        assert resp.status_code == 200

        # Cleanup
        att = Attachment.query.get(att_id)
        if att:
            from app.services import attachment_service
            path = attachment_service.get_attachment_path(att)
            if os.path.exists(path):
                os.remove(path)


class TestDeleteEndpoint:
    """Test DELETE /attachments/<id>."""

    def test_delete_existing_attachment(self, logged_in_client, app, db_session):
        """Test deleting an existing attachment returns 204."""
        # Upload first
        data = {
            "file": _make_file_data("delete_test.jpg"),
            "attachable_type": "service_item",
            "attachable_id": "1",
        }
        upload_resp = logged_in_client.post(
            "/attachments/upload",
            data=data,
            content_type="multipart/form-data",
        )
        att_id = upload_resp.get_json()["id"]

        resp = logged_in_client.delete(f"/attachments/{att_id}")
        assert resp.status_code == 204

        # Verify it's gone
        assert Attachment.query.get(att_id) is None

    def test_delete_nonexistent_returns_404(self, logged_in_client):
        """Test that deleting nonexistent attachment returns 404."""
        resp = logged_in_client.delete("/attachments/99999")
        assert resp.status_code == 404

    def test_delete_requires_admin_or_tech(self, viewer_client):
        """Test that viewer role cannot delete attachments."""
        resp = viewer_client.delete("/attachments/1")
        assert resp.status_code == 403


class TestGalleryEndpoint:
    """Test GET /attachments/gallery/<type>/<id>."""

    def test_gallery_returns_html(self, logged_in_client):
        """Test that gallery endpoint returns HTML fragment."""
        resp = logged_in_client.get("/attachments/gallery/service_item/1")
        assert resp.status_code == 200
        assert b"No images" in resp.data or b"attachment" in resp.data.lower()

    def test_gallery_invalid_type_returns_400(self, logged_in_client):
        """Test that invalid attachable_type returns 400."""
        resp = logged_in_client.get("/attachments/gallery/invalid_type/1")
        assert resp.status_code == 400

    def test_gallery_requires_login(self, client):
        """Test that gallery requires authentication."""
        resp = client.get("/attachments/gallery/service_item/1")
        assert resp.status_code in (302, 401)
