"""Admin blueprint — Settings routes."""

from flask import flash, redirect, render_template, request, url_for
from flask_security import current_user, roles_required

from app.services import audit_service

from app.blueprints.admin import (
    admin_bp,
    _SETTINGS_TABS,
    _get_form_class,
    _handle_logo_uploads,
    _populate_form,
    _save_form,
)


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
