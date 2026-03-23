"""Admin blueprint — User management routes."""

from flask import flash, redirect, render_template, request, url_for
from flask_security import current_user, hash_password, roles_required

from app.extensions import db
from app.models.user import Role, User
from app.services import audit_service, config_service

from app.blueprints.admin import admin_bp, _get_datastore


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
        min_length = config_service.get_config(
            "security.password_min_length", default=8
        )
        errors = []
        if not username:
            errors.append("Username is required.")
        if not email:
            errors.append("Email is required.")
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if not password or len(password) < min_length:
            errors.append(
                f"Password must be at least {min_length} characters."
            )
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

        min_length = config_service.get_config(
            "security.password_min_length", default=8
        )
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
        if password and len(password) < min_length:
            errors.append(
                f"Password must be at least {min_length} characters."
            )

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
    min_length = config_service.get_config(
        "security.password_min_length", default=8
    )
    if not new_password or len(new_password) < min_length:
        flash(
            f"Password must be at least {min_length} characters.", "error"
        )
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
