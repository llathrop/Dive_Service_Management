"""Orders blueprint.

Provides routes for the full service order workflow: listing, creating,
viewing, editing, and deleting service orders, as well as managing
order items, applied services, parts used, labor entries, and service
notes.  All routes require authentication.  Write operations require
the 'admin' or 'technician' role; delete requires 'admin'.

Phase 3 blueprints delegate all business logic to the service layer
(``app.services.order_service``) instead of performing direct DB
operations.
"""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_security import current_user, login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.applied_service import AppliedServiceForm
from app.forms.labor import LaborEntryForm
from app.forms.note import ServiceNoteForm
from app.forms.order import OrderSearchForm, ServiceOrderForm
from app.forms.parts_used import PartUsedForm
from app.forms.service_order_item import ServiceOrderItemForm
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.price_list import PriceListItem
from app.models.service_item import ServiceItem
from app.models.user import Role, User
from app.services import order_service

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")

# Columns that the list view is allowed to sort by.
SORTABLE_FIELDS = {
    "order_number",
    "status",
    "priority",
    "date_received",
    "date_promised",
    "estimated_total",
    "created_at",
}


# ======================================================================
# Helper functions
# ======================================================================


def _get_tech_choices():
    """Return a list of (id, display_name) tuples for admin/technician users."""
    tech_role = Role.query.filter_by(name="technician").first()
    admin_role = Role.query.filter_by(name="admin").first()

    role_ids = [r.id for r in (tech_role, admin_role) if r is not None]
    if not role_ids:
        return []

    users = (
        User.query
        .filter(User.active == True, User.roles.any(Role.id.in_(role_ids)))  # noqa: E712
        .order_by(User.last_name, User.first_name)
        .all()
    )
    return [(u.id, u.display_name) for u in users]


def _populate_order_form_choices(form):
    """Populate dynamic choices on a ServiceOrderForm.

    Sets customer_id choices from non-deleted customers and
    assigned_tech_id choices from users with admin/technician role.
    """
    customers = (
        Customer.not_deleted()
        .order_by(Customer.last_name, Customer.first_name)
        .all()
    )
    form.customer_id.choices = [("", "-- Select --")] + [
        (c.id, c.display_name) for c in customers
    ]
    form.assigned_tech_id.choices = [("", "-- Select --")] + _get_tech_choices()


def _populate_search_form_choices(form):
    """Populate dynamic choices on an OrderSearchForm.

    Sets assigned_tech_id choices from users with admin/technician role.
    """
    form.assigned_tech_id.choices = [("", "All Technicians")] + _get_tech_choices()


def _populate_detail_form_choices(item_form, part_form, labor_form, service_form):
    """Populate dynamic choices for all sub-forms on the detail page.

    Args:
        item_form: ServiceOrderItemForm -- service_item_id choices.
        part_form: PartUsedForm -- inventory_item_id choices.
        labor_form: LaborEntryForm -- tech_id choices.
        service_form: AppliedServiceForm -- price_list_item_id choices.
    """
    # Service items (non-deleted)
    service_items = (
        ServiceItem.not_deleted()
        .order_by(ServiceItem.name)
        .all()
    )
    item_form.service_item_id.choices = [("", "-- Select --")] + [
        (si.id, f"{si.name} ({si.serial_number})" if si.serial_number else si.name)
        for si in service_items
    ]

    # Inventory items (active, non-deleted)
    inv_items = (
        InventoryItem.not_deleted()
        .filter_by(is_active=True)
        .order_by(InventoryItem.name)
        .all()
    )
    part_form.inventory_item_id.choices = [("", "-- Select --")] + [
        (ii.id, f"{ii.name} (SKU: {ii.sku})" if ii.sku else ii.name)
        for ii in inv_items
    ]

    # Technicians (admin/technician role)
    labor_form.tech_id.choices = [("", "-- Select --")] + _get_tech_choices()

    # Price list items (active)
    price_items = (
        PriceListItem.query
        .filter_by(is_active=True)
        .order_by(PriceListItem.name)
        .all()
    )
    service_form.price_list_item_id.choices = [
        ("", "-- Select (or leave blank for custom) --")
    ] + [
        (pi.id, f"{pi.name} (${pi.price})")
        for pi in price_items
    ]


# ======================================================================
# Routes -- Quick Customer Creation
# ======================================================================


@orders_bp.route("/quick-create-customer", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def quick_create_customer():
    """Create a new customer inline and return JSON with id + display_name.

    Accepts form fields: customer_type, first_name, last_name,
    business_name, email, phone_primary.  Returns JSON so the frontend
    can add the new customer to the select dropdown without a page reload.
    """
    customer_type = request.form.get("customer_type", "individual").strip()
    first_name = request.form.get("first_name", "").strip() or None
    last_name = request.form.get("last_name", "").strip() or None
    business_name = request.form.get("business_name", "").strip() or None
    email = request.form.get("email", "").strip() or None
    phone_primary = request.form.get("phone_primary", "").strip() or None

    # Validate required name fields based on customer type
    if customer_type == "business":
        if not business_name:
            return jsonify({"error": "Business name is required."}), 400
    else:
        customer_type = "individual"
        if not first_name or not last_name:
            return jsonify({"error": "First name and last name are required."}), 400

    customer = Customer(
        customer_type=customer_type,
        first_name=first_name,
        last_name=last_name,
        business_name=business_name,
        email=email,
        phone_primary=phone_primary,
    )

    try:
        db.session.add(customer)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "A customer with that email already exists."}), 409

    return jsonify({"id": customer.id, "display_name": customer.display_name}), 201


# ======================================================================
# Routes -- Order CRUD
# ======================================================================


@orders_bp.route("/")
@login_required
def list_orders():
    """List service orders with pagination, search, and filtering."""
    form = OrderSearchForm(request.args)
    _populate_search_form_choices(form)

    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "date_received")
    order = request.args.get("order", "desc")

    # Validate sort field against allowlist
    if sort not in SORTABLE_FIELDS:
        sort = "date_received"

    pagination = order_service.get_orders(
        page=page,
        per_page=25,
        search=form.q.data,
        status=form.status.data,
        priority=form.priority.data,
        assigned_tech_id=form.assigned_tech_id.data,
        date_from=form.date_from.data,
        date_to=form.date_to.data,
        sort=sort,
        order=order,
    )

    return render_template(
        "orders/list.html",
        orders=pagination,
        form=form,
        sort=sort,
        order=order,
    )


@orders_bp.route("/<int:id>")
@login_required
def detail(id):
    """Display a service order detail page with all sub-forms."""
    order = order_service.get_order(id)
    summary = order_service.get_order_summary(id)

    # Create sub-forms for the detail page
    item_form = ServiceOrderItemForm()
    service_form = AppliedServiceForm()
    part_form = PartUsedForm()
    labor_form = LaborEntryForm()
    note_form = ServiceNoteForm()

    _populate_detail_form_choices(item_form, part_form, labor_form, service_form)

    return render_template(
        "orders/detail.html",
        order=order,
        summary=summary,
        item_form=item_form,
        service_form=service_form,
        part_form=part_form,
        labor_form=labor_form,
        note_form=note_form,
    )


@orders_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def create():
    """Show new service order form (GET) or create an order (POST)."""
    form = ServiceOrderForm()
    _populate_order_form_choices(form)

    if form.validate_on_submit():
        data = {
            "customer_id": form.customer_id.data,
            "status": form.status.data,
            "priority": form.priority.data,
            "assigned_tech_id": form.assigned_tech_id.data,
            "date_received": form.date_received.data,
            "date_promised": form.date_promised.data,
            "description": form.description.data,
            "internal_notes": form.internal_notes.data,
            "estimated_total": form.estimated_total.data,
            "rush_fee": form.rush_fee.data,
            "discount_percent": form.discount_percent.data,
            "discount_amount": form.discount_amount.data,
        }
        try:
            new_order = order_service.create_order(
                data, created_by=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
            flash("Service order created successfully.", "success")
            return redirect(url_for("orders.detail", id=new_order.id))
        except IntegrityError:
            db.session.rollback()
            flash("A service order with that number already exists.", "error")

    return render_template("orders/form.html", form=form, is_edit=False)


@orders_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def edit(id):
    """Show edit service order form (GET) or update the order (POST)."""
    order = order_service.get_order(id)
    form = ServiceOrderForm(obj=order)
    _populate_order_form_choices(form)

    if form.validate_on_submit():
        # Status is not included here — use the change_status route instead.
        data = {
            "customer_id": form.customer_id.data,
            "priority": form.priority.data,
            "assigned_tech_id": form.assigned_tech_id.data,
            "date_received": form.date_received.data,
            "date_promised": form.date_promised.data,
            "description": form.description.data,
            "internal_notes": form.internal_notes.data,
            "estimated_total": form.estimated_total.data,
            "rush_fee": form.rush_fee.data,
            "discount_percent": form.discount_percent.data,
            "discount_amount": form.discount_amount.data,
        }
        try:
            order_service.update_order(
                id, data,
                user_id=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
            flash("Service order updated successfully.", "success")
            return redirect(url_for("orders.detail", id=id))
        except IntegrityError:
            db.session.rollback()
            flash("A service order with that number already exists.", "error")

    return render_template(
        "orders/form.html", form=form, order=order, is_edit=True
    )


@orders_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
@roles_accepted("admin")
def delete(id):
    """Soft-delete a service order (admin only)."""
    order_service.delete_order(
        id,
        user_id=current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )
    flash("Service order deleted.", "success")
    return redirect(url_for("orders.list_orders"))


# ======================================================================
# Routes -- Status Workflow
# ======================================================================


@orders_bp.route("/<int:id>/status", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def change_status(id):
    """Transition a service order to a new status."""
    new_status = request.form.get("new_status", "").strip()
    if not new_status:
        flash("No status provided.", "error")
        return redirect(url_for("orders.detail", id=id))

    order, success = order_service.change_status(
        id, new_status, current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )
    if success:
        flash(f"Order status changed to {order.display_status}.", "success")
    else:
        flash(
            f"Cannot transition from '{order.display_status}' "
            f"to '{new_status.replace('_', ' ').title()}'.",
            "error",
        )
    return redirect(url_for("orders.detail", id=id))


# ======================================================================
# Routes -- Order Items
# ======================================================================


@orders_bp.route("/<int:id>/items/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_item(id):
    """Add a service item to a service order."""
    form = ServiceOrderItemForm()

    # Populate choices so validation passes
    service_items = ServiceItem.not_deleted().order_by(ServiceItem.name).all()
    form.service_item_id.choices = [("", "-- Select --")] + [
        (si.id, si.name) for si in service_items
    ]

    if form.validate_on_submit():
        try:
            order_service.add_order_item(
                order_id=id,
                service_item_id=form.service_item_id.data,
                work_description=form.work_description.data,
                condition_at_receipt=form.condition_at_receipt.data,
            )
            flash("Item added to order.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    return redirect(url_for("orders.detail", id=id))


@orders_bp.route("/items/<int:item_id>/remove", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def remove_item(item_id):
    """Remove a service item from a service order."""
    order_item = order_service.get_order_item(item_id)
    if order_item is None:
        flash("Order item not found.", "error")
        return redirect(url_for("orders.list_orders"))

    order_id = order_item.order_id
    order_service.remove_order_item(item_id)
    flash("Item removed from order.", "success")
    return redirect(url_for("orders.detail", id=order_id))


# ======================================================================
# Routes -- Applied Services
# ======================================================================


@orders_bp.route("/items/<int:item_id>/services/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_service(item_id):
    """Add an applied service to a service order item."""
    form = AppliedServiceForm()

    # Populate choices so validation passes
    price_items = PriceListItem.query.filter_by(is_active=True).order_by(PriceListItem.name).all()
    form.price_list_item_id.choices = [
        ("", "-- Select (or leave blank for custom) --")
    ] + [(pi.id, pi.name) for pi in price_items]

    if form.validate_on_submit():
        data = {
            "price_list_item_id": form.price_list_item_id.data,
            "service_name": form.service_name.data,
            "service_description": form.service_description.data,
            "quantity": form.quantity.data,
            "unit_price": form.unit_price.data,
            "discount_percent": form.discount_percent.data,
            "is_taxable": form.is_taxable.data,
            "notes": form.notes.data,
        }
        order_service.add_applied_service(item_id, data, added_by=current_user.id)
        flash("Service added.", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    # Navigate back to the parent order's detail page
    order_item = order_service.get_order_item(item_id)
    order_id = order_item.order_id if order_item else None
    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))


@orders_bp.route("/services/<int:service_id>/remove", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def remove_service(service_id):
    """Remove an applied service from a service order item."""
    from app.models.applied_service import AppliedService

    applied = db.session.get(AppliedService, service_id)
    if applied is None:
        flash("Applied service not found.", "error")
        return redirect(url_for("orders.list_orders"))

    # Get the order_id before deletion
    order_item = order_service.get_order_item(applied.service_order_item_id)
    order_id = order_item.order_id if order_item else None

    order_service.remove_applied_service(service_id)
    flash("Service removed.", "success")

    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))


# ======================================================================
# Routes -- Parts Used
# ======================================================================


@orders_bp.route("/items/<int:item_id>/parts/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_part(item_id):
    """Add a part (inventory item) to a service order item."""
    form = PartUsedForm()

    # Populate choices so validation passes
    inv_items = (
        InventoryItem.not_deleted()
        .filter_by(is_active=True)
        .order_by(InventoryItem.name)
        .all()
    )
    form.inventory_item_id.choices = [("", "-- Select --")] + [
        (ii.id, ii.name) for ii in inv_items
    ]

    if form.validate_on_submit():
        try:
            order_service.add_part_used(
                order_item_id=item_id,
                inventory_item_id=form.inventory_item_id.data,
                quantity=form.quantity.data,
                unit_price_at_use=form.unit_price_at_use.data,
                notes=form.notes.data,
                added_by=current_user.id,
            )
            flash("Part added.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    # Navigate back to the parent order's detail page
    order_item = order_service.get_order_item(item_id)
    order_id = order_item.order_id if order_item else None
    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))


@orders_bp.route("/parts/<int:part_id>/remove", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def remove_part(part_id):
    """Remove a part used record and restore inventory."""
    from app.models.parts_used import PartUsed

    part = db.session.get(PartUsed, part_id)
    if part is None:
        flash("Part record not found.", "error")
        return redirect(url_for("orders.list_orders"))

    # Get the order_id before deletion
    order_item = order_service.get_order_item(part.service_order_item_id)
    order_id = order_item.order_id if order_item else None

    order_service.remove_part_used(part_id)
    flash("Part removed.", "success")

    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))


# ======================================================================
# Routes -- Labor Entries
# ======================================================================


@orders_bp.route("/items/<int:item_id>/labor/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_labor(item_id):
    """Add a labor entry to a service order item."""
    form = LaborEntryForm()

    # Populate choices so validation passes
    form.tech_id.choices = [("", "-- Select --")] + _get_tech_choices()

    if form.validate_on_submit():
        try:
            order_service.add_labor_entry(
                order_item_id=item_id,
                tech_id=form.tech_id.data,
                hours=form.hours.data,
                hourly_rate=form.hourly_rate.data,
                description=form.description.data,
                work_date=form.work_date.data,
            )
            flash("Labor entry added.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    # Navigate back to the parent order's detail page
    order_item = order_service.get_order_item(item_id)
    order_id = order_item.order_id if order_item else None
    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))


@orders_bp.route("/labor/<int:labor_id>/remove", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def remove_labor(labor_id):
    """Remove a labor entry."""
    from app.models.labor import LaborEntry

    entry = db.session.get(LaborEntry, labor_id)
    if entry is None:
        flash("Labor entry not found.", "error")
        return redirect(url_for("orders.list_orders"))

    # Get the order_id before deletion
    order_item = order_service.get_order_item(entry.service_order_item_id)
    order_id = order_item.order_id if order_item else None

    order_service.remove_labor_entry(labor_id)
    flash("Labor entry removed.", "success")

    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))


# ======================================================================
# Routes -- Service Notes
# ======================================================================


@orders_bp.route("/items/<int:item_id>/notes/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_note(item_id):
    """Add a note to a service order item."""
    form = ServiceNoteForm()

    if form.validate_on_submit():
        try:
            order_service.add_service_note(
                order_item_id=item_id,
                note_text=form.note_text.data,
                note_type=form.note_type.data,
                created_by=current_user.id,
            )
            flash("Note added.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    # Navigate back to the parent order's detail page
    order_item = order_service.get_order_item(item_id)
    order_id = order_item.order_id if order_item else None
    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))
