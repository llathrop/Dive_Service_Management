"""Tests for the Attachment model."""

import pytest
from datetime import datetime, timezone

from app.models.attachment import Attachment
from tests.factories import AttachmentFactory, UserFactory


class TestAttachmentModel:
    """Test Attachment model creation and properties."""

    def test_create_attachment_all_fields(self, db_session):
        """Test creating an attachment with all fields populated."""
        AttachmentFactory._meta.sqlalchemy_session = db_session
        UserFactory._meta.sqlalchemy_session = db_session

        user = UserFactory()
        att = AttachmentFactory(uploaded_by=user.id)

        assert att.id is not None
        assert att.attachable_type == "service_item"
        assert att.attachable_id is not None
        assert att.filename is not None
        assert att.stored_filename is not None
        assert att.file_path is not None
        assert att.file_size > 0
        assert att.mime_type == "image/jpeg"
        assert att.uploaded_by == user.id
        assert att.created_at is not None

    def test_attachment_is_image_property(self, db_session):
        """Test the is_image property for different MIME types."""
        AttachmentFactory._meta.sqlalchemy_session = db_session

        img_att = AttachmentFactory(mime_type="image/jpeg")
        assert img_att.is_image is True

        png_att = AttachmentFactory(mime_type="image/png")
        assert png_att.is_image is True

        pdf_att = AttachmentFactory(mime_type="application/pdf")
        assert pdf_att.is_image is False

    def test_attachment_repr(self, db_session):
        """Test the __repr__ method."""
        AttachmentFactory._meta.sqlalchemy_session = db_session

        att = AttachmentFactory(filename="test.jpg", attachable_type="service_item", attachable_id=42)
        assert "test.jpg" in repr(att)
        assert "service_item" in repr(att)
        assert "42" in repr(att)

    def test_attachment_uploader_relationship(self, db_session):
        """Test the uploader relationship to User."""
        AttachmentFactory._meta.sqlalchemy_session = db_session
        UserFactory._meta.sqlalchemy_session = db_session

        user = UserFactory()
        att = AttachmentFactory(uploaded_by=user.id)

        assert att.uploader is not None
        assert att.uploader.id == user.id

    def test_attachment_nullable_fields(self, db_session):
        """Test that description and uploaded_by are nullable."""
        AttachmentFactory._meta.sqlalchemy_session = db_session

        att = AttachmentFactory(description=None, uploaded_by=None)
        assert att.id is not None
        assert att.description is None
        assert att.uploaded_by is None

    def test_attachment_timestamp_mixin(self, db_session):
        """Test that TimestampMixin provides created_at."""
        AttachmentFactory._meta.sqlalchemy_session = db_session

        att = AttachmentFactory()
        assert att.created_at is not None

    def test_attachment_indexes_exist(self, db_session):
        """Test that expected indexes are defined on the model."""
        indexes = {idx.name for idx in Attachment.__table__.indexes}
        assert "ix_attachments_attachable" in indexes
        assert "ix_attachments_mime_type" in indexes
