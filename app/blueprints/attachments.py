"""Attachments blueprint for file upload, serving, and management.

Provides REST-style endpoints for uploading, viewing, deleting, and
browsing file attachments on service items and service order items.
Upload and delete require admin or technician role; viewing requires
login only.
"""

import os

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_security import current_user, login_required, roles_accepted

from app.services import attachment_service

attachments_bp = Blueprint("attachments", __name__, url_prefix="/attachments")

# Valid attachable types
VALID_ATTACHABLE_TYPES = {"service_item", "service_order_item"}


@attachments_bp.route("/upload", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def upload():
    """Upload a file attachment.

    Expects multipart form data with:
    - file: The file to upload
    - attachable_type: Entity type ('service_item' or 'service_order_item')
    - attachable_id: Entity ID
    - description: Optional description

    Returns JSON with attachment details or error.
    """
    file = request.files.get("file")
    attachable_type = request.form.get("attachable_type", "").strip()
    attachable_id = request.form.get("attachable_id", type=int)
    description = request.form.get("description", "").strip() or None

    # Validate required fields
    if not file:
        return jsonify({"error": "No file provided."}), 400
    if attachable_type not in VALID_ATTACHABLE_TYPES:
        return jsonify({"error": f"Invalid attachable_type. Must be one of: {', '.join(sorted(VALID_ATTACHABLE_TYPES))}"}), 400
    if not attachable_id:
        return jsonify({"error": "attachable_id is required."}), 400

    try:
        attachment = attachment_service.save_attachment(
            file=file,
            attachable_type=attachable_type,
            attachable_id=attachable_id,
            description=description,
            uploaded_by=current_user.id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "id": attachment.id,
        "filename": attachment.filename,
        "url": url_for("attachments.serve_file", id=attachment.id),
        "thumbnail_url": url_for("attachments.thumbnail", id=attachment.id),
        "mime_type": attachment.mime_type,
        "file_size": attachment.file_size,
        "is_image": attachment.is_image,
        "description": attachment.description,
    }), 201


@attachments_bp.route("/<int:id>/file")
@login_required
def serve_file(id):
    """Serve an attachment file.

    Validates the attachment exists in the DB before serving to
    prevent path traversal attacks.
    """
    attachment = attachment_service.get_attachment(id)
    if not attachment:
        abort(404)

    abs_path = attachment_service.get_attachment_path(attachment)
    if not os.path.exists(abs_path):
        abort(404)

    return send_file(
        abs_path,
        mimetype=attachment.mime_type,
        as_attachment=False,
        download_name=attachment.filename,
    )


@attachments_bp.route("/<int:id>/thumbnail")
@login_required
def thumbnail(id):
    """Serve a thumbnail of an attachment.

    For images, attempts to resize to max 200px wide using Pillow.
    If Pillow is not available or the file is not an image, serves
    the original file.
    """
    attachment = attachment_service.get_attachment(id)
    if not attachment:
        abort(404)

    abs_path = attachment_service.get_attachment_path(attachment)
    if not os.path.exists(abs_path):
        abort(404)

    # Only attempt thumbnail generation for images
    if attachment.is_image:
        try:
            from PIL import Image
            import io

            img = Image.open(abs_path)
            # Maintain aspect ratio, max 200px wide
            max_width = 200
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            # Convert to bytes
            buf = io.BytesIO()
            img_format = "JPEG" if attachment.mime_type == "image/jpeg" else "PNG"
            if img.mode in ("RGBA", "P") and img_format == "JPEG":
                img = img.convert("RGB")
            img.save(buf, format=img_format, quality=85)
            buf.seek(0)

            return send_file(
                buf,
                mimetype=attachment.mime_type,
                as_attachment=False,
            )
        except ImportError:
            # Pillow not available — serve original
            pass
        except Exception:
            # Any image processing error — serve original
            pass

    # Fallback: serve the original file
    return send_file(
        abs_path,
        mimetype=attachment.mime_type,
        as_attachment=False,
        download_name=attachment.filename,
    )


@attachments_bp.route("/<int:id>", methods=["DELETE"])
@login_required
@roles_accepted("admin", "technician")
def delete(id):
    """Delete an attachment (file + DB record).

    Returns 204 on success, 404 if not found.
    """
    deleted = attachment_service.delete_attachment(id)
    if not deleted:
        abort(404)
    return "", 204


@attachments_bp.route("/gallery/<attachable_type>/<int:attachable_id>")
@login_required
def gallery(attachable_type, attachable_id):
    """Return an HTML fragment of the attachment gallery for HTMX loading.

    This is designed to be loaded via hx-get into a container element.
    """
    if attachable_type not in VALID_ATTACHABLE_TYPES:
        abort(400)

    attachments = attachment_service.get_attachments(attachable_type, attachable_id)
    can_edit = current_user.has_role("admin") or current_user.has_role("technician")

    return render_template(
        "attachments/gallery_fragment.html",
        attachments=attachments,
        attachable_type=attachable_type,
        attachable_id=attachable_id,
        can_edit=can_edit,
    )


@attachments_bp.route("/gallery/unified/<int:service_item_id>")
@login_required
def unified_gallery(service_item_id):
    """Return an HTML fragment with the unified photo history for a service item.

    Combines direct item attachments with photos from all service order
    items referencing this equipment.  Designed to be loaded via hx-get.
    """
    direct, order_attachments = attachment_service.get_unified_attachments(
        service_item_id
    )

    return render_template(
        "partials/unified_gallery.html",
        direct_attachments=direct,
        order_attachments=order_attachments,
        service_item_id=service_item_id,
    )
