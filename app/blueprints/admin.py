"""Admin blueprint.

Provides user management, system settings, and data management
pages. All routes require the 'admin' role.
"""

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


# ── User Management ────────────────────────────────────────────────

@admin_bp.route("/users")
@roles_required("admin")
def list_users():
    """List all users with their roles and status."""
    users = User.query.order_by(User.username).all()
    return render_template("admin/users/list.html", users=users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@roles_required("admin")
def create_user():
    """Create a new user."""
    roles = Role.query.order_by(Role.name).all()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        password = request.form.get("password", "")
        role_ids = request.form.getlist("roles")

        # Validation
        errors = []
        if not username:
            errors.append("Username is required.")
        if not email:
            errors.append("Email is required.")
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if not password or len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if User.query.filter_by(username=username).first():
            errors.append("Username already exists.")
        if User.query.filter_by(email=email).first():
            errors.append("Email already exists.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/users/form.html",
                roles=roles,
                form_data=request.form,
                is_edit=False,
            )

        user_datastore = _get_datastore()
        user = user_datastore.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=hash_password(password),
        )
        for rid in role_ids:
            role = db.session.get(Role, int(rid))
            if role:
                user_datastore.add_role_to_user(user, role)
        db.session.commit()
        try:
            audit_service.log_action(
                action="create",
                entity_type="user",
                entity_id=user.id,
                user_id=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
        except Exception:
            pass
        flash(f"User '{username}' created successfully.", "success")
        return redirect(url_for("admin.list_users"))

    return render_template(
        "admin/users/form.html",
        roles=roles,
        form_data={},
        is_edit=False,
    )


@admin_bp.route("/users/<int:id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_user(id):
    """Edit an existing user."""
    user = db.session.get(User, id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.list_users"))

    roles = Role.query.order_by(Role.name).all()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        password = request.form.get("password", "")
        role_ids = request.form.getlist("roles")

        errors = []
        if not username:
            errors.append("Username is required.")
        if not email:
            errors.append("Email is required.")
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        existing = User.query.filter_by(username=username).first()
        if existing and existing.id != user.id:
            errors.append("Username already exists.")
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != user.id:
            errors.append("Email already exists.")
        if password and len(password) < 8:
            errors.append("Password must be at least 8 characters.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "admin/users/form.html",
                roles=roles,
                form_data=request.form,
                user=user,
                is_edit=True,
            )

        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        if password:
            user.password = hash_password(password)

        # Update roles
        user_datastore = _get_datastore()
        current_roles = set(user.roles)
        selected_roles = set()
        for rid in role_ids:
            role = db.session.get(Role, int(rid))
            if role:
                selected_roles.add(role)

        for role in current_roles - selected_roles:
            user_datastore.remove_role_from_user(user, role)
        for role in selected_roles - current_roles:
            user_datastore.add_role_to_user(user, role)

        db.session.commit()
        try:
            audit_service.log_action(
                action="update",
                entity_type="user",
                entity_id=user.id,
                user_id=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
        except Exception:
            pass
        flash(f"User '{username}' updated successfully.", "success")
        return redirect(url_for("admin.list_users"))

    return render_template(
        "admin/users/form.html",
        roles=roles,
        form_data={},
        user=user,
        is_edit=True,
    )


@admin_bp.route("/users/<int:id>/toggle-active", methods=["POST"])
@roles_required("admin")
def toggle_user_active(id):
    """Activate or deactivate a user."""
    user = db.session.get(User, id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.list_users"))

    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin.list_users"))

    user_datastore = _get_datastore()
    old_active = user.active
    if user.active:
        user_datastore.deactivate_user(user)
        flash(f"User '{user.username}' deactivated.", "success")
    else:
        user_datastore.activate_user(user)
        flash(f"User '{user.username}' activated.", "success")
    db.session.commit()
    try:
        audit_service.log_action(
            action="update",
            entity_type="user",
            entity_id=user.id,
            user_id=current_user.id,
            field_name="active",
            old_value=str(old_active),
            new_value=str(user.active),
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except Exception:
        pass
    return redirect(url_for("admin.list_users"))


@admin_bp.route("/users/<int:id>/reset-password", methods=["POST"])
@roles_required("admin")
def reset_password(id):
    """Reset a user's password to a provided value."""
    user = db.session.get(User, id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.list_users"))

    new_password = request.form.get("new_password", "")
    if not new_password or len(new_password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("admin.edit_user", id=id))

    user.password = hash_password(new_password)
    db.session.commit()
    try:
        audit_service.log_action(
            action="update",
            entity_type="user",
            entity_id=user.id,
            user_id=current_user.id,
            field_name="password",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except Exception:
        pass
    flash(f"Password reset for '{user.username}'.", "success")
    return redirect(url_for("admin.list_users"))


# ── System Settings ─────────────────────────────────────────────────

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


@admin_bp.route("/settings", methods=["GET", "POST"])
@roles_required("admin")
def settings():
    """System settings — tabbed form with all categories."""
    from app.services import config_service

    active_tab = request.args.get("tab", "company")
    if active_tab not in _SETTINGS_TABS:
        active_tab = "company"

    # Build all forms (for rendering all tabs)
    forms = {}
    for tab_key in _SETTINGS_TABS:
        FormClass = _get_form_class(tab_key)
        if request.method == "POST" and request.form.get("tab") == tab_key:
            forms[tab_key] = FormClass()
        else:
            forms[tab_key] = FormClass(formdata=None)
            _populate_form(forms[tab_key], tab_key)

    if request.method == "POST":
        submitted_tab = request.form.get("tab", "company")
        if submitted_tab in forms and forms[submitted_tab].validate_on_submit():
            count = _save_form(
                forms[submitted_tab], submitted_tab, current_user.id
            )
            # Handle logo file uploads for company tab
            if submitted_tab == "company":
                logo_count = _handle_logo_uploads(
                    forms[submitted_tab], current_user.id
                )
                count += logo_count
            try:
                audit_service.log_action(
                    action="update",
                    entity_type="system_config",
                    entity_id=0,
                    user_id=current_user.id,
                    field_name=submitted_tab,
                    new_value=f"{count} values saved",
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
            flash(f"Settings updated ({count} values saved).", "success")
            return redirect(url_for("admin.settings", tab=submitted_tab))
        else:
            active_tab = submitted_tab

    # Build env-locked info for template
    locked_keys = {}
    for tab_key, tab_info in _SETTINGS_TABS.items():
        for config_key in tab_info["fields"]:
            if config_service.is_env_locked(config_key):
                locked_keys[config_key] = True

    return render_template(
        "admin/settings.html",
        forms=forms,
        tabs=_SETTINGS_TABS,
        active_tab=active_tab,
        locked_keys=locked_keys,
    )


# ── Data Management ─────────────────────────────────────────────────

@admin_bp.route("/data")
@roles_required("admin")
def data_management():
    """Data management hub with live DB stats, backup, export, migration info."""
    from app.services import data_management_service

    table_stats = data_management_service.get_table_stats()
    db_version = data_management_service.get_db_version()
    db_size = data_management_service.get_db_size()
    migration = data_management_service.get_migration_status()

    # Summary stats for the top cards
    stats = {}
    for entry in table_stats:
        stats[entry["table"]] = entry["rows"]

    return render_template(
        "admin/data.html",
        table_stats=table_stats,
        db_version=db_version,
        db_size=db_size,
        migration=migration,
        stats=stats,
    )


@admin_bp.route("/data/backup")
@roles_required("admin")
def download_backup():
    """Download a SQL backup of the database."""
    from datetime import datetime
    from flask import Response
    from app.services import data_management_service

    try:
        sql_dump = data_management_service.create_backup_sql()
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("admin.data_management"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dsm_backup_{timestamp}.sql"

    return Response(
        sql_dump,
        mimetype="application/sql",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Audit Log ───────────────────────────────────────────────────────

@admin_bp.route("/audit-log")
@roles_required("admin")
def audit_log():
    """View the audit log with filtering and pagination."""
    from datetime import datetime
    from app.services import audit_service
    from app.models.user import User

    # Parse filter parameters
    entity_type = request.args.get("entity_type", "").strip() or None
    action = request.args.get("action", "").strip() or None
    user_id = request.args.get("user_id", type=int)
    page = request.args.get("page", 1, type=int)

    date_from = None
    date_from_str = request.args.get("date_from", "").strip()
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
        except ValueError:
            pass

    date_to = None
    date_to_str = request.args.get("date_to", "").strip()
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        except ValueError:
            pass

    pagination = audit_service.get_audit_logs(
        entity_type=entity_type,
        entity_id=None,
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=50,
    )

    users = User.query.order_by(User.username).all()

    entity_types = [
        "customer", "service_order", "service_item", "inventory_item",
        "invoice", "payment", "price_list_item", "user",
    ]
    actions = [
        "create", "update", "delete", "restore", "login", "logout",
        "export", "status_change",
    ]

    return render_template(
        "admin/audit_log.html",
        pagination=pagination,
        logs=pagination.items,
        users=users,
        entity_types=entity_types,
        actions=actions,
        filters={
            "entity_type": entity_type or "",
            "action": action or "",
            "user_id": user_id or "",
            "date_from": date_from_str,
            "date_to": date_to_str,
        },
    )


# ── CSV Import ──────────────────────────────────────────────────────

VALID_IMPORT_TYPES = {"customers", "inventory"}


@admin_bp.route("/data/import", methods=["GET", "POST"])
@roles_required("admin")
def import_data():
    """CSV import page — upload, preview, and confirm import."""
    from app.services import import_service

    entity_type = request.args.get("type", "customers")
    if entity_type not in VALID_IMPORT_TYPES:
        entity_type = "customers"

    if request.method == "POST":
        action = request.form.get("action", "preview")
        entity_type = request.form.get("entity_type", "customers")

        if action == "preview":
            file = request.files.get("csv_file")
            if not file or not file.filename:
                flash("Please select a CSV file to upload.", "error")
                return redirect(url_for("admin.import_data", type=entity_type))

            content = file.read().decode("utf-8-sig")
            result = import_service.parse_csv(content, entity_type)

            return render_template(
                "admin/import_preview.html",
                entity_type=entity_type,
                result=result,
                csv_content=content,
            )

        elif action == "confirm":
            content = request.form.get("csv_content", "")
            result = import_service.parse_csv(content, entity_type)

            if result["errors"]:
                flash(f"Import has {len(result['errors'])} validation error(s). Fix the CSV and try again.", "error")
                return render_template(
                    "admin/import_preview.html",
                    entity_type=entity_type,
                    result=result,
                    csv_content=content,
                )

            if entity_type == "customers":
                outcome = import_service.import_customers(result["rows"])
            else:
                outcome = import_service.import_inventory(result["rows"])

            if outcome["errors"]:
                for err in outcome["errors"]:
                    flash(f"Row {err['row']}: {err['message']}", "error")

            flash(
                f"Import complete: {outcome['imported']} imported, "
                f"{outcome['skipped']} skipped (duplicates).",
                "success",
            )
            return redirect(url_for("admin.data_management"))

    return render_template(
        "admin/import_form.html",
        entity_type=entity_type,
    )


# ── Import Wizard (Column Mapping) ───────────────────────────────────

VALID_WIZARD_TYPES = {"customers", "inventory"}
ALLOWED_IMPORT_EXTENSIONS = {".csv", ".xlsx"}


@admin_bp.route("/import/wizard")
@roles_required("admin")
def import_wizard():
    """Import wizard — Step 1: Upload file."""
    entity_type = request.args.get("type", "customers")
    if entity_type not in VALID_WIZARD_TYPES:
        entity_type = "customers"

    return render_template(
        "admin/import_mapping.html",
        step="upload",
        entity_type=entity_type,
    )


@admin_bp.route("/import/upload", methods=["POST"])
@roles_required("admin")
def import_wizard_upload():
    """Handle file upload, detect columns, and show mapping step."""
    from app.services import import_service

    entity_type = request.form.get("entity_type", "customers")
    if entity_type not in VALID_WIZARD_TYPES:
        entity_type = "customers"

    file = request.files.get("import_file")
    if not file or not file.filename:
        flash("Please select a file to upload.", "error")
        return redirect(url_for("admin.import_wizard", type=entity_type))

    filename = file.filename.lower()
    if not any(filename.endswith(ext) for ext in ALLOWED_IMPORT_EXTENSIONS):
        flash("Invalid file type. Please upload a CSV or XLSX file.", "error")
        return redirect(url_for("admin.import_wizard", type=entity_type))

    # Determine file type
    file_type = "xlsx" if filename.endswith(".xlsx") else "csv"

    # Read file content
    raw_bytes = file.read()

    if file_type == "csv":
        try:
            file_content = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            flash("Unable to read CSV file. Ensure it is UTF-8 encoded.", "error")
            return redirect(url_for("admin.import_wizard", type=entity_type))
        detect_content = file_content
    else:
        detect_content = raw_bytes

    # Detect columns
    source_columns = import_service.detect_columns(detect_content, file_type)
    if not source_columns:
        flash("Could not detect any columns in the uploaded file.", "error")
        return redirect(url_for("admin.import_wizard", type=entity_type))

    # Get target fields and auto-detect mapping
    target_fields = import_service.get_target_fields(entity_type)
    auto_mapping = import_service.auto_detect_mapping(source_columns, entity_type)

    # Build sample values (first non-empty value per column)
    sample_values = _extract_sample_values(detect_content, file_type, source_columns)

    # Encode file content as base64 for hidden form field
    file_content_b64 = base64.b64encode(raw_bytes).decode("ascii")

    return render_template(
        "admin/import_mapping.html",
        step="mapping",
        entity_type=entity_type,
        source_columns=source_columns,
        target_fields=target_fields,
        auto_mapping=auto_mapping,
        sample_values=sample_values,
        file_content_b64=file_content_b64,
        file_type=file_type,
    )


@admin_bp.route("/import/preview", methods=["POST"])
@roles_required("admin")
def import_wizard_preview():
    """Apply column mapping and show preview."""
    from app.services import import_service

    entity_type = request.form.get("entity_type", "customers")
    if entity_type not in VALID_WIZARD_TYPES:
        entity_type = "customers"

    file_content_b64 = request.form.get("file_content", "")
    file_type = request.form.get("file_type", "csv")

    if not file_content_b64:
        flash("File content missing. Please start over.", "error")
        return redirect(url_for("admin.import_wizard", type=entity_type))

    # Decode file content
    try:
        raw_bytes = base64.b64decode(file_content_b64)
    except Exception:
        flash("Invalid file data. Please start over.", "error")
        return redirect(url_for("admin.import_wizard", type=entity_type))

    if file_type == "csv":
        file_content = raw_bytes.decode("utf-8-sig")
    else:
        file_content = raw_bytes

    # Reconstruct column mapping from form
    column_mapping = _extract_mapping_from_form(request.form)

    # Validate and preview
    result = import_service.map_and_validate(
        file_content, column_mapping, entity_type, file_type
    )

    return render_template(
        "admin/import_mapping.html",
        step="preview",
        entity_type=entity_type,
        result=result,
        column_mapping=column_mapping,
        file_content_b64=file_content_b64,
        file_type=file_type,
    )


@admin_bp.route("/import/execute", methods=["POST"])
@roles_required("admin")
def import_wizard_execute():
    """Execute the import with the confirmed mapping."""
    from app.services import import_service

    entity_type = request.form.get("entity_type", "customers")
    if entity_type not in VALID_WIZARD_TYPES:
        entity_type = "customers"

    file_content_b64 = request.form.get("file_content", "")
    file_type = request.form.get("file_type", "csv")

    if not file_content_b64:
        flash("File content missing. Please start over.", "error")
        return redirect(url_for("admin.import_wizard", type=entity_type))

    try:
        raw_bytes = base64.b64decode(file_content_b64)
    except Exception:
        flash("Invalid file data. Please start over.", "error")
        return redirect(url_for("admin.import_wizard", type=entity_type))

    if file_type == "csv":
        file_content = raw_bytes.decode("utf-8-sig")
    else:
        file_content = raw_bytes

    # Reconstruct column mapping from form
    sources = request.form.getlist("map_source[]")
    targets = request.form.getlist("map_target[]")
    column_mapping = {}
    for source, target in zip(sources, targets):
        column_mapping[source] = target if target else None

    # Execute import
    outcome = import_service.execute_mapped_import(
        file_content, column_mapping, entity_type, file_type
    )

    try:
        audit_service.log_action(
            action="create",
            entity_type=entity_type,
            entity_id=0,
            user_id=current_user.id,
            field_name="import",
            new_value=f"{outcome['imported']} imported, {outcome['skipped']} skipped",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except Exception:
        pass

    return render_template(
        "admin/import_mapping.html",
        step="result",
        entity_type=entity_type,
        outcome=outcome,
    )


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


# ── Helpers ─────────────────────────────────────────────────────────

def _get_datastore():
    """Get the Flask-Security user datastore from the current app."""
    from flask import current_app
    return current_app.extensions["security"].datastore
