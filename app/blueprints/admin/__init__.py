"""Admin blueprint — package layout."""

import base64
import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_security import current_user, hash_password, roles_required
from sqlalchemy import func
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.user import Role, User
from app.services import audit_service

# Maximum logo file size: 2 MB
_MAX_LOGO_SIZE = 2 * 1024 * 1024
_ALLOWED_LOGO_EXTENSIONS = {"jpg", "jpeg", "png"}

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Hub ─────────────────────────────────────────────────────────────

@admin_bp.route("/")
@roles_required("admin")
def hub():
    """Admin hub — landing page with links to admin functions."""
    user_count = db.session.query(func.count(User.id)).scalar()
    role_count = db.session.query(func.count(Role.id)).scalar()
    return render_template(
        "admin/hub.html",
        user_count=user_count,
        role_count=role_count,
    )


# ── System Settings Shared Config ──────────────────────────────────

# Form class → list of (config_key, form_field_name) mappings
_SETTINGS_TABS = {
    "company": {
        "label": "Company",
        "icon": "bi-building",
        "fields": {
            "company.name": "company_name",
            "company.address": "company_address",
            "company.phone": "company_phone",
            "company.email": "company_email",
            "company.website": "company_website",
            "company.logo_path": "logo_upload",
            "company.invoice_logo_path": "invoice_logo_upload",
        },
    },
    "service": {
        "label": "Service",
        "icon": "bi-wrench",
        "fields": {
            "service.order_prefix": "order_prefix",
            "service.default_labor_rate": "default_labor_rate",
            "service.rush_fee_default": "rush_fee_default",
        },
    },
    "invoice_tax": {
        "label": "Invoice & Tax",
        "icon": "bi-receipt",
        "fields": {
            "invoice.prefix": "invoice_prefix",
            "invoice.default_terms": "default_terms",
            "invoice.default_due_days": "default_due_days",
            "invoice.footer_text": "footer_text",
            "tax.default_rate": "tax_rate",
            "tax.label": "tax_label",
        },
    },
    "display": {
        "label": "Display",
        "icon": "bi-palette",
        "fields": {
            "display.date_format": "date_format",
            "display.currency_symbol": "currency_symbol",
            "display.currency_code": "currency_code",
            "display.pagination_size": "pagination_size",
        },
    },
    "notification": {
        "label": "Notifications",
        "icon": "bi-bell",
        "fields": {
            "notification.low_stock_check_hours": "low_stock_check_hours",
            "notification.overdue_check_time": "overdue_check_time",
            "notification.retention_days": "retention_days",
            "notification.order_due_warning_days": "order_due_warning_days",
        },
    },
    "email": {
        "label": "Email",
        "icon": "bi-envelope",
        "fields": {
            "email.enabled": "email_enabled",
            "email.smtp_server": "smtp_server",
            "email.smtp_port": "smtp_port",
            "email.smtp_use_tls": "smtp_use_tls",
            "email.smtp_username": "smtp_username",
            "email.smtp_password": "smtp_password",
            "email.from_address": "from_address",
            "email.from_name": "from_name",
        },
    },
    "security": {
        "label": "Security",
        "icon": "bi-shield-lock",
        "fields": {
            "security.password_min_length": "password_min_length",
            "security.lockout_attempts": "lockout_attempts",
            "security.lockout_duration_minutes": "lockout_duration_minutes",
            "security.session_lifetime_hours": "session_lifetime_hours",
        },
    },
}

_FORM_CLASSES = {
    "company": "CompanySettingsForm",
    "service": "ServiceSettingsForm",
    "invoice_tax": "InvoiceTaxSettingsForm",
    "display": "DisplaySettingsForm",
    "notification": "NotificationSettingsForm",
    "email": "EmailSettingsForm",
    "security": "SecuritySettingsForm",
}


def _get_form_class(tab_key):
    """Import and return the form class for a settings tab."""
    import app.forms.settings as settings_forms
    return getattr(settings_forms, _FORM_CLASSES[tab_key])


def _populate_form(form, tab_key):
    """Fill a form with current config values from the database."""
    from wtforms import PasswordField as WTPasswordField
    from app.services import config_service

    fields = _SETTINGS_TABS[tab_key]["fields"]
    for config_key, field_name in fields.items():
        field = getattr(form, field_name, None)
        if field is not None:
            # Never populate password fields — they always render blank
            if isinstance(field, WTPasswordField):
                continue
            value = config_service.get_config(config_key)
            if value is not None:
                field.data = value


def _save_form(form, tab_key, user_id):
    """Save form data back to config_service.

    FileField entries are skipped here — they are handled separately
    in ``_handle_logo_uploads()``.  PasswordField entries with empty
    values are also skipped so "leave blank = keep current" works.
    """
    from flask_wtf.file import FileField as WTFileField
    from wtforms import PasswordField as WTPasswordField
    from app.services import config_service

    fields = _SETTINGS_TABS[tab_key]["fields"]
    updates = {}
    for config_key, field_name in fields.items():
        field = getattr(form, field_name, None)
        if field is None or isinstance(field, WTFileField):
            continue
        # Skip empty password fields (means "keep current value")
        if isinstance(field, WTPasswordField) and not field.data:
            continue
        updates[config_key] = field.data
    return config_service.bulk_set(updates, user_id=user_id)


def _handle_logo_uploads(form, user_id):
    """Process logo file uploads from the company settings form.

    Saves valid files to ``uploads/logos/`` and updates the corresponding
    config keys.  Returns the number of logos saved.
    """
    from app.services import config_service

    upload_map = {
        "logo_upload": "company.logo_path",
        "invoice_logo_upload": "company.invoice_logo_path",
    }

    logos_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "logos")
    os.makedirs(logos_dir, exist_ok=True)

    count = 0
    for field_name, config_key in upload_map.items():
        field = getattr(form, field_name, None)
        if field is None or not field.data or not hasattr(field.data, "filename"):
            continue

        file = field.data
        if not file.filename:
            continue

        # Validate extension
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in _ALLOWED_LOGO_EXTENSIONS:
            flash(f"Invalid file type for {field.label.text}. Use JPG or PNG.", "error")
            continue

        # Validate size (read content, check length, seek back)
        content = file.read()
        if len(content) > _MAX_LOGO_SIZE:
            flash(f"{field.label.text} exceeds 2 MB limit.", "error")
            continue

        # Validate magic bytes to prevent disguised file uploads
        _MAGIC_BYTES = {
            b"\xff\xd8\xff": "jpg",      # JPEG
            b"\x89PNG": "png",            # PNG
        }
        is_valid_image = any(content.startswith(magic) for magic in _MAGIC_BYTES)
        if not is_valid_image:
            flash(f"{field.label.text} does not appear to be a valid image file.", "error")
            continue
        file.seek(0)

        # Save with safe filename
        safe_name = secure_filename(file.filename)
        # Prefix to avoid collisions: header_ or invoice_
        prefix = "header_" if field_name == "logo_upload" else "invoice_"
        dest_name = prefix + safe_name
        dest_path = os.path.join(logos_dir, dest_name)
        file.save(dest_path)

        # Store relative path (from UPLOAD_FOLDER) in config
        rel_path = os.path.join("logos", dest_name)
        config_service.set_config(config_key, rel_path, user_id=user_id)
        count += 1

    return count


# ── Shared Helpers ──────────────────────────────────────────────────

def _get_datastore():
    """Get the Flask-Security user datastore from the current app."""
    from flask import current_app
    return current_app.extensions["security"].datastore


# ── CSV Import Shared Constants ─────────────────────────────────────

VALID_IMPORT_TYPES = {"customers", "inventory"}
VALID_WIZARD_TYPES = {"customers", "inventory"}
ALLOWED_IMPORT_EXTENSIONS = {".csv", ".xlsx"}


def _extract_mapping_from_form(form):
    """Extract column mapping from form submission.

    Form fields: source_col_0, source_col_1, ... and mapping_0, mapping_1, ...
    """
    column_mapping = {}
    i = 0
    while True:
        source_key = f"source_col_{i}"
        mapping_key = f"mapping_{i}"
        source = form.get(source_key)
        if source is None:
            break
        target = form.get(mapping_key, "")
        column_mapping[source] = target if target else None
        i += 1
    return column_mapping


def _extract_sample_values(file_content, file_type, source_columns):
    """Get first non-empty sample value for each source column."""
    from app.services.import_service import _read_rows

    headers, raw_rows = _read_rows(file_content, file_type)
    sample_values = {}

    # Build header->index mapping
    header_idx = {}
    for idx, h in enumerate(headers):
        header_idx[h] = idx

    for col in source_columns:
        idx = header_idx.get(col)
        if idx is None:
            sample_values[col] = ""
            continue
        # Get first 3 non-empty values
        samples = []
        for row in raw_rows[:5]:
            if idx < len(row) and row[idx].strip():
                samples.append(row[idx].strip())
            if len(samples) >= 3:
                break
        sample_values[col] = ", ".join(samples)

    return sample_values


# Import submodules to register their routes on admin_bp
from app.blueprints.admin import users, settings, data, audit, logs  # noqa: E402, F401
