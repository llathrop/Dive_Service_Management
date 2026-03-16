"""Tests for the attachment service."""

import os
import io
import pytest
from unittest.mock import patch

from app.models.attachment import Attachment
from app.services import attachment_service
from tests.factories import AttachmentFactory, UserFactory


def _make_file(filename="test.jpg", content=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
               content_type="image/jpeg"):
    """Create a mock FileStorage-like object."""
    from werkzeug.datastructures import FileStorage
    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type=content_type,
    )


class TestValidateFile:
    """Test file validation logic."""

    def test_valid_jpeg(self, app):
        """Test that a valid JPEG file passes validation."""
        with app.app_context():
            file = _make_file("photo.jpg")
            valid, error, mime = attachment_service.validate_file(file)
            assert valid is True
            assert error is None
            assert mime == "image/jpeg"

    def test_valid_png(self, app):
        """Test that a valid PNG file passes validation."""
        with app.app_context():
            file = _make_file("image.png", content_type="image/png")
            valid, error, mime = attachment_service.validate_file(file)
            assert valid is True
            assert mime == "image/png"

    def test_valid_pdf(self, app):
        """Test that a valid PDF file passes validation."""
        with app.app_context():
            file = _make_file("doc.pdf", content=b"%PDF-1.4" + b"\x00" * 100,
                              content_type="application/pdf")
            valid, error, mime = attachment_service.validate_file(file)
            assert valid is True
            assert mime == "application/pdf"

    def test_invalid_extension_rejected(self, app):
        """Test that disallowed file extensions are rejected."""
        with app.app_context():
            file = _make_file("malware.exe", content_type="application/octet-stream")
            valid, error, mime = attachment_service.validate_file(file)
            assert valid is False
            assert "not allowed" in error

    def test_empty_file_rejected(self, app):
        """Test that empty files are rejected."""
        with app.app_context():
            file = _make_file("empty.jpg", content=b"")
            valid, error, mime = attachment_service.validate_file(file)
            assert valid is False
            assert "empty" in error.lower()

    def test_no_file_rejected(self, app):
        """Test that None/missing file is rejected."""
        with app.app_context():
            valid, error, mime = attachment_service.validate_file(None)
            assert valid is False

    def test_file_size_exceeds_limit(self, app):
        """Test that oversized files are rejected."""
        with app.app_context():
            # Set a very small limit for testing
            app.config["MAX_CONTENT_LENGTH"] = 100
            big_content = b"\xff\xd8\xff\xe0" + b"\x00" * 200
            file = _make_file("big.jpg", content=big_content)
            valid, error, mime = attachment_service.validate_file(file)
            assert valid is False
            assert "exceeds" in error.lower()


class TestSaveAttachment:
    """Test saving attachments to disk and DB."""

    def test_save_creates_record_and_file(self, app, db_session):
        """Test that save_attachment creates both a DB record and file on disk."""
        with app.app_context():
            file = _make_file("photo.jpg")
            att = attachment_service.save_attachment(
                file=file,
                attachable_type="service_item",
                attachable_id=1,
                description="Test photo",
                uploaded_by=None,
            )

            assert att.id is not None
            assert att.filename == "photo.jpg"
            assert att.mime_type == "image/jpeg"
            assert att.description == "Test photo"
            assert att.file_size > 0

            # Check file exists on disk
            abs_path = attachment_service.get_attachment_path(att)
            assert os.path.exists(abs_path)

            # Cleanup
            os.remove(abs_path)

    def test_save_generates_uuid_filename(self, app, db_session):
        """Test that stored filenames are UUID-based and unique."""
        with app.app_context():
            file1 = _make_file("photo.jpg")
            att1 = attachment_service.save_attachment(
                file=file1, attachable_type="service_item", attachable_id=1,
            )
            file2 = _make_file("photo.jpg")
            att2 = attachment_service.save_attachment(
                file=file2, attachable_type="service_item", attachable_id=1,
            )

            assert att1.stored_filename != att2.stored_filename
            assert att1.stored_filename.endswith(".jpg")
            assert att2.stored_filename.endswith(".jpg")

            # Cleanup
            for att in [att1, att2]:
                p = attachment_service.get_attachment_path(att)
                if os.path.exists(p):
                    os.remove(p)

    def test_save_invalid_file_raises_valueerror(self, app, db_session):
        """Test that invalid files raise ValueError."""
        with app.app_context():
            file = _make_file("bad.exe")
            with pytest.raises(ValueError, match="not allowed"):
                attachment_service.save_attachment(
                    file=file, attachable_type="service_item", attachable_id=1,
                )

    def test_save_creates_directory_structure(self, app, db_session):
        """Test that the year/month directory structure is created."""
        with app.app_context():
            file = _make_file("photo.jpg")
            att = attachment_service.save_attachment(
                file=file, attachable_type="service_item", attachable_id=1,
            )

            assert "service_item" in att.file_path
            # Path should contain year/month components
            parts = att.file_path.split(os.sep)
            assert "attachments" in parts

            # Cleanup
            abs_path = attachment_service.get_attachment_path(att)
            if os.path.exists(abs_path):
                os.remove(abs_path)


class TestGetAttachments:
    """Test attachment retrieval."""

    def test_get_attachments_returns_matching(self, app, db_session):
        """Test that get_attachments returns only matching attachments."""
        with app.app_context():
            # Create two attachments for different entities
            file1 = _make_file("a.jpg")
            att1 = attachment_service.save_attachment(
                file=file1, attachable_type="service_item", attachable_id=1,
            )
            file2 = _make_file("b.jpg")
            att2 = attachment_service.save_attachment(
                file=file2, attachable_type="service_item", attachable_id=2,
            )

            results = attachment_service.get_attachments("service_item", 1)
            assert len(results) == 1
            assert results[0].id == att1.id

            # Cleanup
            for att in [att1, att2]:
                p = attachment_service.get_attachment_path(att)
                if os.path.exists(p):
                    os.remove(p)

    def test_get_attachment_by_id(self, app, db_session):
        """Test getting a single attachment by ID."""
        with app.app_context():
            file = _make_file("c.jpg")
            att = attachment_service.save_attachment(
                file=file, attachable_type="service_item", attachable_id=1,
            )

            result = attachment_service.get_attachment(att.id)
            assert result is not None
            assert result.id == att.id

            # Cleanup
            p = attachment_service.get_attachment_path(att)
            if os.path.exists(p):
                os.remove(p)

    def test_get_attachment_nonexistent_returns_none(self, app, db_session):
        """Test that nonexistent attachment returns None."""
        with app.app_context():
            assert attachment_service.get_attachment(99999) is None


class TestDeleteAttachment:
    """Test attachment deletion."""

    def test_delete_removes_file_and_record(self, app, db_session):
        """Test that delete removes both the file and DB record."""
        with app.app_context():
            file = _make_file("d.jpg")
            att = attachment_service.save_attachment(
                file=file, attachable_type="service_item", attachable_id=1,
            )
            att_id = att.id
            abs_path = attachment_service.get_attachment_path(att)
            assert os.path.exists(abs_path)

            deleted = attachment_service.delete_attachment(att_id)
            assert deleted is True
            assert not os.path.exists(abs_path)
            assert attachment_service.get_attachment(att_id) is None

    def test_delete_nonexistent_returns_false(self, app, db_session):
        """Test that deleting a nonexistent attachment returns False."""
        with app.app_context():
            assert attachment_service.delete_attachment(99999) is False
