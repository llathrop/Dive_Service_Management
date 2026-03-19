"""Orders blueprint — Order item and quick-create customer routes."""

from flask import flash, jsonify, redirect, request, url_for
from flask_security import login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.service_order_item import ServiceOrderItemForm
from app.models.customer import Customer
from app.models.service_item import ServiceItem
from app.services import audit_service, order_service

from app.blueprints.orders import orders_bp


@orders_bp.route("/quick-create-customer", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def quick_create_customer():
    """Create a new customer inline and return JSON with id + display_name."""
    customer_type = request.form.get("customer_type", "individual").strip()
    first_name = request.form.get("first_name", "").strip() or None
    last_name = request.form.get("last_name", "").strip() or None
    business_name = request.form.get("business_name", "").strip() or None
    email = request.form.get("email", "").strip() or None
    phone_primary = request.form.get("phone_primary", "").strip() or None

    # Validate input lengths
    if first_name and len(first_name) > 100:
        return jsonify({"error": "First name exceeds 100 characters."}), 400
    if last_name and len(last_name) > 100:
        return jsonify({"error": "Last name exceeds 100 characters."}), 400
    if business_name and len(business_name) > 200:
        return jsonify({"error": "Business name exceeds 200 characters."}), 400
    if email and len(email) > 254:
        return jsonify({"error": "Email exceeds 254 characters."}), 400
    if phone_primary and len(phone_primary) > 30:
        return jsonify({"error": "Phone number exceeds 30 characters."}), 400

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

    try:
        audit_service.log_action(
            action="create",
            entity_type="customer",
            entity_id=customer.id,
            details={"name": customer.display_name, "source": "quick_create"},
        )
    except Exception:
        pass

    return jsonify({"id": customer.id, "display_name": customer.display_name}), 201


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
