"""Orders blueprint — CRUD routes, kanban view, and shared helpers.

Submodules (items, services, parts, labor, notes, status) are imported
at the bottom of this file to register their routes on ``orders_bp``.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
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
from app.models.service_order import ServiceOrder
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
    """Populate dynamic choices on a ServiceOrderForm."""
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
    """Populate dynamic choices on an OrderSearchForm."""
    form.assigned_tech_id.choices = [("", "All Technicians")] + _get_tech_choices()


def _populate_detail_form_choices(item_form, part_form, labor_form, service_form):
    """Populate dynamic choices for all sub-forms on the detail page."""
    # Service items (non-deleted)
    service_items = (
        ServiceItem.not_deleted()
        .order_by(ServiceItem.name)
        .all()
    )
    item_form.service_item_id.choices = [
        ("", "-- Select --"),
        ("__new__", "+ Create New Service Item"),
    ] + [
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
    part_form.inventory_item_id.choices = [
        ("", "-- Select --"),
        ("__new__", "+ Create New Inventory Item"),
    ] + [
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
        ("", "-- Select (or leave blank for custom) --"),
        ("__new__", "+ Create New Price List Item"),
    ] + [
        (pi.id, f"{pi.name} (${pi.price})")
        for pi in price_items
    ]


# Active statuses shown as columns on the kanban board (excludes terminal states).
KANBAN_ACTIVE_STATUSES = [
    "intake",
    "assessment",
    "awaiting_approval",
    "in_progress",
    "awaiting_parts",
    "completed",
    "ready_for_pickup",
]

KANBAN_STATUS_LABELS = {
    "intake": "Intake",
    "assessment": "Assessment",
    "awaiting_approval": "Awaiting Approval",
    "in_progress": "In Progress",
    "awaiting_parts": "Awaiting Parts",
    "completed": "Completed",
    "ready_for_pickup": "Ready for Pickup",
    "picked_up": "Picked Up",
    "cancelled": "Cancelled",
}


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


@orders_bp.route("/kanban")
@login_required
@roles_accepted("admin", "technician")
def kanban():
    """Display the Kanban board view for service orders."""
    # Fetch all non-deleted orders
    all_orders = ServiceOrder.not_deleted().all()

    # Group orders by status
    columns = {s: [] for s in KANBAN_ACTIVE_STATUSES}
    archived_orders = {"picked_up": [], "cancelled": []}

    for o in all_orders:
        if o.status in columns:
            columns[o.status].append(o)
        elif o.status in archived_orders:
            archived_orders[o.status].append(o)

    total_count = sum(len(v) for v in columns.values())
    archived_count = sum(len(v) for v in archived_orders.values())

    return render_template(
        "orders/kanban.html",
        columns=columns,
        archived_orders=archived_orders,
        active_statuses=KANBAN_ACTIVE_STATUSES,
        status_labels=KANBAN_STATUS_LABELS,
        total_count=total_count,
        archived_count=archived_count,
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


# Import submodules to register their routes on orders_bp
from app.blueprints.orders import items, services, parts, labor, notes, status  # noqa: E402, F401
