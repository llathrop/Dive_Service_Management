"""Admin blueprint — Data management routes."""

import base64

from flask import flash, redirect, render_template, request, url_for
from flask_security import current_user, roles_required

from app.services import audit_service

from app.blueprints.admin import (
    admin_bp,
    ALLOWED_IMPORT_EXTENSIONS,
    VALID_IMPORT_TYPES,
    VALID_WIZARD_TYPES,
    _extract_mapping_from_form,
    _extract_sample_values,
)


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

    try:
        audit_service.log_action(
            action="download_backup",
            entity_type="system",
            entity_id=0,
            user_id=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except Exception:
        pass

    return Response(
        sql_dump,
        mimetype="application/sql",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── CSV Import ──────────────────────────────────────────────────────

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
