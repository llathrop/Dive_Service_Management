"""Admin blueprint.

Provides user management, system settings, and data management
pages. All routes require the 'admin' role.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_security import current_user, hash_password, roles_required
from sqlalchemy import func

from app.extensions import db
from app.models.user import Role, User

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
    if user.active:
        user_datastore.deactivate_user(user)
        flash(f"User '{user.username}' deactivated.", "success")
    else:
        user_datastore.activate_user(user)
        flash(f"User '{user.username}' activated.", "success")
    db.session.commit()
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
    "security": "SecuritySettingsForm",
}


def _get_form_class(tab_key):
    """Import and return the form class for a settings tab."""
    import app.forms.settings as settings_forms
    return getattr(settings_forms, _FORM_CLASSES[tab_key])


def _populate_form(form, tab_key):
    """Fill a form with current config values from the database."""
    from app.services import config_service

    fields = _SETTINGS_TABS[tab_key]["fields"]
    for config_key, field_name in fields.items():
        field = getattr(form, field_name, None)
        if field is not None:
            value = config_service.get_config(config_key)
            if value is not None:
                field.data = value


def _save_form(form, tab_key, user_id):
    """Save form data back to config_service."""
    from app.services import config_service

    fields = _SETTINGS_TABS[tab_key]["fields"]
    updates = {}
    for config_key, field_name in fields.items():
        field = getattr(form, field_name, None)
        if field is not None:
            updates[config_key] = field.data
    return config_service.bulk_set(updates, user_id=user_id)


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


# ── Helpers ─────────────────────────────────────────────────────────

def _get_datastore():
    """Get the Flask-Security user datastore from the current app."""
    from flask import current_app
    return current_app.extensions["security"].datastore
