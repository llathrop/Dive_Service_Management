"""Orders blueprint — Service order template routes.

Provides CRUD for reusable service order templates and an apply-to-order
endpoint.  All routes are registered on the shared ``orders_bp`` blueprint.
"""

import json

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_security import current_user, login_required, roles_accepted

from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.price_list import PriceListItem
from app.models.service_order_template import ServiceOrderTemplate
from app.services import template_service

from app.blueprints.orders import orders_bp


# ======================================================================
# Template list
# ======================================================================

@orders_bp.route("/templates")
@login_required
@roles_accepted("admin", "technician")
def list_templates():
    """List all templates visible to the current user."""
    templates = template_service.get_templates(
        user_id=current_user.id, include_shared=True,
    )
    return render_template("orders/templates/list.html", templates=templates)


# ======================================================================
# Template create
# ======================================================================

@orders_bp.route("/templates/new", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def create_template():
    """Show template creation form (GET) or create a template (POST)."""
    price_items = (
        PriceListItem.query.filter_by(is_active=True)
        .order_by(PriceListItem.name)
        .all()
    )
    inv_items = (
        InventoryItem.not_deleted()
        .filter_by(is_active=True)
        .order_by(InventoryItem.name)
        .all()
    )

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        is_shared = request.form.get("is_shared") == "on"

        template_data, parse_errors = _build_template_data_from_form(request.form)
        if parse_errors:
            for error in parse_errors:
                flash(error, "error")
            return render_template(
                "orders/templates/form.html",
                is_edit=False,
                template=None,
                price_items=price_items,
                inv_items=inv_items,
                form_data=request.form,
            )

        if not name:
            flash("Template name is required.", "error")
            return render_template(
                "orders/templates/form.html",
                is_edit=False,
                template=None,
                price_items=price_items,
                inv_items=inv_items,
                form_data=request.form,
            )

        try:
            template = template_service.create_template(
                name=name,
                description=description or None,
                created_by_id=current_user.id,
                is_shared=is_shared,
                template_data=template_data,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
            flash("Template created successfully.", "success")
            return redirect(url_for("orders.template_detail", id=template.id))
        except ValueError as e:
            flash(str(e), "error")

    return render_template(
        "orders/templates/form.html",
        is_edit=False,
        template=None,
        price_items=price_items,
        inv_items=inv_items,
        form_data={},
    )


# ======================================================================
# Template detail
# ======================================================================

@orders_bp.route("/templates/<int:id>")
@login_required
@roles_accepted("admin", "technician")
def template_detail(id):
    """Show template details."""
    template = template_service.get_template(id, user_id=current_user.id)

    # Resolve names for display
    data = template.template_data or {}
    services_display = []
    for svc in data.get("services", []):
        pli = db.session.get(PriceListItem, svc.get("price_list_item_id"))
        services_display.append({
            "name": pli.name if pli else "Unknown Service",
            "quantity": svc.get("quantity", 1),
            "override_price": svc.get("override_price"),
        })

    parts_display = []
    for part in data.get("parts", []):
        inv = db.session.get(InventoryItem, part.get("inventory_item_id"))
        parts_display.append({
            "name": inv.name if inv else "Unknown Item",
            "quantity": part.get("quantity", 1),
        })

    return render_template(
        "orders/templates/detail.html",
        template=template,
        services_display=services_display,
        parts_display=parts_display,
    )


# ======================================================================
# Template edit
# ======================================================================

@orders_bp.route("/templates/<int:id>/edit", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def edit_template(id):
    """Show template edit form (GET) or update a template (POST)."""
    template = db.session.get(ServiceOrderTemplate, id)
    if template is None or template.created_by_id != current_user.id:
        abort(404)
    price_items = (
        PriceListItem.query.filter_by(is_active=True)
        .order_by(PriceListItem.name)
        .all()
    )
    inv_items = (
        InventoryItem.not_deleted()
        .filter_by(is_active=True)
        .order_by(InventoryItem.name)
        .all()
    )

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        is_shared = request.form.get("is_shared") == "on"
        template_data, parse_errors = _build_template_data_from_form(request.form)
        if parse_errors:
            for error in parse_errors:
                flash(error, "error")
            return render_template(
                "orders/templates/form.html",
                is_edit=True,
                template=template,
                price_items=price_items,
                inv_items=inv_items,
                form_data=request.form,
            )

        if not name:
            flash("Template name is required.", "error")
            return render_template(
                "orders/templates/form.html",
                is_edit=True,
                template=template,
                price_items=price_items,
                inv_items=inv_items,
                form_data=request.form,
            )

        try:
            template_service.update_template(
                id,
                name=name,
                description=description or None,
                is_shared=is_shared,
                template_data=template_data,
                user_id=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
            flash("Template updated successfully.", "success")
            return redirect(url_for("orders.template_detail", id=id))
        except ValueError as e:
            flash(str(e), "error")

    return render_template(
        "orders/templates/form.html",
        is_edit=True,
        template=template,
        price_items=price_items,
        inv_items=inv_items,
        form_data={},
    )


# ======================================================================
# Template delete
# ======================================================================

@orders_bp.route("/templates/<int:id>/delete", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def delete_template(id):
    """Delete a template."""
    template_service.delete_template(
        id,
        user_id=current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )
    flash("Template deleted.", "success")
    return redirect(url_for("orders.list_templates"))


# ======================================================================
# Apply template to order
# ======================================================================

@orders_bp.route("/templates/<int:id>/apply/<int:order_id>", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def apply_template(id, order_id):
    """Apply a template to an existing service order."""
    try:
        summary = template_service.apply_template(
            order_id=order_id,
            template_id=id,
            user_id=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("orders.detail", id=order_id))

    parts = []
    if summary["fields_updated"]:
        parts.append(f"Updated: {', '.join(summary['fields_updated'])}")
    if summary["services_added"]:
        parts.append(f"{summary['services_added']} service(s) added")
    if summary["parts_added"]:
        parts.append(f"{summary['parts_added']} part(s) added")

    msg = "Template applied. " + "; ".join(parts) if parts else "Template applied (no changes)."
    flash(msg, "success")
    return redirect(url_for("orders.detail", id=order_id))


# ======================================================================
# Template preview (JSON for HTMX load-from-template)
# ======================================================================

@orders_bp.route("/templates/<int:id>/preview")
@login_required
@roles_accepted("admin", "technician")
def preview_template(id):
    """Return template data as JSON for form pre-population."""
    template = template_service.get_template(id, user_id=current_user.id)
    return jsonify({
        "id": template.id,
        "name": template.name,
        "template_data": template.template_data,
    })


# ======================================================================
# Helpers
# ======================================================================

def _build_template_data_from_form(form):
    """Extract template_data dict from a multidict form submission.

    Expects form fields like:
      - priority, rush_fee, discount_percent, notes, estimated_labor_hours
      - service_pli_id[], service_qty[], service_price[]
      - part_inv_id[], part_qty[]

    Returns:
        A tuple of (template_data, errors).
    """
    data = {}
    errors = []

    if form.get("priority"):
        data["priority"] = form["priority"]
    if form.get("rush_fee"):
        data["rush_fee"] = form["rush_fee"]
    if form.get("discount_percent"):
        data["discount_percent"] = form["discount_percent"]
    if form.get("notes"):
        data["notes"] = form["notes"]
    if form.get("estimated_labor_hours"):
        data["estimated_labor_hours"] = form["estimated_labor_hours"]

    # Services
    pli_ids = form.getlist("service_pli_id[]")
    svc_qtys = form.getlist("service_qty[]")
    svc_prices = form.getlist("service_price[]")
    services = []
    for i, pli_id in enumerate(pli_ids):
        if pli_id:
            try:
                parsed_pli_id = int(pli_id)
            except (TypeError, ValueError):
                errors.append("Service entries must use valid numeric service IDs.")
                continue

            svc = {"price_list_item_id": parsed_pli_id, "quantity": 1}
            if i < len(svc_qtys) and svc_qtys[i]:
                try:
                    svc["quantity"] = int(svc_qtys[i])
                except (TypeError, ValueError):
                    errors.append("Service quantities must be whole numbers.")
                    continue
            if i < len(svc_prices) and svc_prices[i]:
                svc["override_price"] = svc_prices[i]
            else:
                svc["override_price"] = None
            services.append(svc)
    if services:
        data["services"] = services

    # Parts
    inv_ids = form.getlist("part_inv_id[]")
    part_qtys = form.getlist("part_qty[]")
    parts = []
    for i, inv_id in enumerate(inv_ids):
        if inv_id:
            try:
                parsed_inv_id = int(inv_id)
            except (TypeError, ValueError):
                errors.append("Part entries must use valid numeric inventory IDs.")
                continue

            part = {"inventory_item_id": parsed_inv_id, "quantity": 1}
            if i < len(part_qtys) and part_qtys[i]:
                try:
                    part["quantity"] = int(part_qtys[i])
                except (TypeError, ValueError):
                    errors.append("Part quantities must be whole numbers.")
                    continue
            parts.append(part)
    if parts:
        data["parts"] = parts

    return data, errors
