"""Attachment model for file uploads (images, PDFs) on any entity.

Supports polymorphic associations via ``attachable_type`` and
``attachable_id``, allowing attachments on service items, service
order items, or any future entity type.
"""

from app.extensions import db
from app.models.mixins import TimestampMixin


class Attachment(TimestampMixin, db.Model):
    """A file attachment associated with any attachable entity."""

    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)

    # Polymorphic association
    attachable_type = db.Column(db.String(50), nullable=False)  # 'service_item', 'service_order_item'
    attachable_id = db.Column(db.Integer, nullable=False)

    # File metadata
    filename = db.Column(db.String(255), nullable=False)        # original filename
    stored_filename = db.Column(db.String(255), nullable=False)  # UUID-based unique name
    file_path = db.Column(db.String(500), nullable=False)       # relative path within uploads/
    file_size = db.Column(db.Integer, nullable=False)           # bytes
    mime_type = db.Column(db.String(100), nullable=False)

    # Optional description
    description = db.Column(db.String(500), nullable=True)

    # Who uploaded it
    uploaded_by = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )

    # Relationships
    uploader = db.relationship("User", backref="attachments")

    __table_args__ = (
        db.Index("ix_attachments_attachable", "attachable_type", "attachable_id"),
        db.Index("ix_attachments_mime_type", "mime_type"),
    )

    @property
    def is_image(self):
        """Return True if this attachment is an image."""
        return self.mime_type.startswith("image/") if self.mime_type else False

    def __repr__(self):
        return f"<Attachment {self.id} {self.filename} ({self.attachable_type}#{self.attachable_id})>"
