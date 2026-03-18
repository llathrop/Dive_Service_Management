"""Admin blueprint — Log viewer routes."""

from flask import render_template, request
from flask_security import roles_required

from app.blueprints.admin import admin_bp


@admin_bp.route("/logs")
@roles_required("admin")
def logs():
    """Admin log viewer page."""
    from app.services import log_service

    available_logs = log_service.get_available_logs()
    selected = request.args.get("log", "app")
    line_count = request.args.get("lines", 200, type=int)

    result = log_service.read_log(selected, lines=line_count)

    return render_template(
        "admin/logs.html",
        available_logs=available_logs,
        selected_log=selected,
        line_count=line_count,
        result=result,
    )


@admin_bp.route("/logs/tail")
@roles_required("admin")
def logs_tail():
    """HTMX endpoint for log tail polling."""
    from app.services import log_service

    selected = request.args.get("log", "app")
    line_count = request.args.get("lines", 200, type=int)

    result = log_service.read_log(selected, lines=line_count)

    return render_template(
        "admin/_log_content.html",
        result=result,
    )
