"""Attachment service for managing file uploads.

Handles validation, storage, and retrieval of file attachments.
Files are stored on disk under the configured UPLOAD_FOLDER with
UUID-based filenames to prevent collisions.
"""

import os
import uuid
from datetime import datetime, timezone

from flask import current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.attachment import Attachment
from app.models.service_order_item import ServiceOrderItem

# Allowed MIME types for upload
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
}

# Extension-to-MIME mapping for validation
ALLOWED_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def _get_upload_base():
    """Return the base upload directory from app config."""
    return current_app.config.get(
        "UPLOAD_FOLDER",
        os.path.join(current_app.root_path, "..", "uploads"),
    )


def _get_max_size():
    """Return the maximum upload size in bytes from config."""
    return current_app.config.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)


def validate_file(file):
    """Validate an uploaded file's type and size.

    Args:
        file: A Werkzeug ``FileStorage`` object.

    Returns:
        tuple: (is_valid, error_message, mime_type)
    """
    if not file or not file.filename:
        return False, "No file provided.", None

    # Check extension
    original_name = secure_filename(file.filename)
    _, ext = os.path.splitext(original_name)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS.keys()))}", None

    mime_type = ALLOWED_EXTENSIONS[ext]

    # Also check Content-Type header if provided
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        # Be lenient with Content-Type since browsers can be unreliable;
        # trust the extension if it's in our allowlist
        pass

    # Check file size by reading content length
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    max_size = _get_max_size()
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"File size ({file_size} bytes) exceeds maximum ({max_mb:.0f} MB).", None

    if file_size == 0:
        return False, "File is empty.", None

    return True, None, mime_type


def save_attachment(file, attachable_type, attachable_id, description=None, uploaded_by=None):
    """Save an uploaded file and create an Attachment record.

    Args:
        file: A Werkzeug ``FileStorage`` object.
        attachable_type: Entity type (e.g. 'service_item', 'service_order_item').
        attachable_id: ID of the entity.
        description: Optional description text.
        uploaded_by: User ID of the uploader.

    Returns:
        Attachment: The created attachment record.

    Raises:
        ValueError: If file validation fails.
    """
    is_valid, error, mime_type = validate_file(file)
    if not is_valid:
        raise ValueError(error)

    # Generate UUID-based filename
    original_name = secure_filename(file.filename)
    _, ext = os.path.splitext(original_name)
    ext = ext.lower()
    stored_filename = f"{uuid.uuid4().hex}{ext}"

    # Build directory path: uploads/attachments/<type>/<year>/<month>/
    now = datetime.now(timezone.utc)
    relative_dir = os.path.join(
        "attachments", attachable_type, str(now.year), f"{now.month:02d}"
    )
    abs_dir = os.path.join(_get_upload_base(), relative_dir)
    os.makedirs(abs_dir, exist_ok=True)

    # Save file to disk
    abs_path = os.path.join(abs_dir, stored_filename)
    file.seek(0)
    file.save(abs_path)

    # Get actual file size from saved file
    file_size = os.path.getsize(abs_path)

    # Relative path for DB storage
    relative_path = os.path.join(relative_dir, stored_filename)

    # Create DB record
    attachment = Attachment(
        attachable_type=attachable_type,
        attachable_id=attachable_id,
        filename=original_name,
        stored_filename=stored_filename,
        file_path=relative_path,
        file_size=file_size,
        mime_type=mime_type,
        description=description,
        uploaded_by=uploaded_by,
    )
    db.session.add(attachment)
    db.session.commit()

    return attachment


def get_attachments(attachable_type, attachable_id):
    """Return all attachments for a given entity.

    Args:
        attachable_type: Entity type string.
        attachable_id: Entity ID.

    Returns:
        list[Attachment]: Attachments ordered by creation date descending.
    """
    return (
        Attachment.query
        .filter_by(attachable_type=attachable_type, attachable_id=attachable_id)
        .order_by(Attachment.created_at.desc())
        .all()
    )


def get_attachment(attachment_id):
    """Return a single attachment by ID.

    Args:
        attachment_id: The attachment's primary key.

    Returns:
        Attachment or None.
    """
    return db.session.get(Attachment, attachment_id)


def delete_attachment(attachment_id):
    """Delete an attachment's file from disk and its DB record.

    Args:
        attachment_id: The attachment's primary key.

    Returns:
        bool: True if deleted, False if not found.
    """
    attachment = db.session.get(Attachment, attachment_id)
    if not attachment:
        return False

    # Remove file from disk
    abs_path = os.path.join(_get_upload_base(), attachment.file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)

    # Remove DB record
    db.session.delete(attachment)
    db.session.commit()
    return True


def get_unified_attachments(service_item_id):
    """Return all attachments for a service item and its service order items.

    Provides a complete visual history by combining direct item photos
    with photos taken during service visits.

    Args:
        service_item_id: ID of the ServiceItem.

    Returns:
        tuple: (direct_attachments, order_attachments) where
            direct_attachments is a list of Attachment objects for the item,
            order_attachments is a list of dicts with keys 'order_item',
            'order', and 'attachments' for each service order item that
            has attachments.
    """
    # Direct attachments on the service item
    direct = (
        Attachment.query
        .filter_by(attachable_type="service_item", attachable_id=service_item_id)
        .order_by(Attachment.created_at.desc())
        .all()
    )

    # Find all service order items referencing this equipment
    order_items = (
        ServiceOrderItem.query
        .filter_by(service_item_id=service_item_id)
        .all()
    )

    # Collect attachments for each order item that has any
    order_attachments = []
    for oi in order_items:
        atts = (
            Attachment.query
            .filter_by(attachable_type="service_order_item", attachable_id=oi.id)
            .order_by(Attachment.created_at.desc())
            .all()
        )
        if atts:
            order_attachments.append({
                "order_item": oi,
                "order": oi.order,
                "attachments": atts,
            })

    return direct, order_attachments


def get_attachment_path(attachment):
    """Return the absolute file path for an attachment.

    Args:
        attachment: An Attachment instance.

    Returns:
        str: Absolute path to the file on disk.
    """
    return os.path.join(_get_upload_base(), attachment.file_path)
