"""Customers blueprint.

Provides routes for listing, creating, viewing, editing, and soft-deleting
customer records.  All routes require authentication.  Write operations
(create, edit, delete) require the 'admin' or 'technician' role.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import current_user, login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.customer import CustomerForm, CustomerSearchForm
from app.models.customer import Customer

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")

# Columns that the list view is allowed to sort by.
SORTABLE_FIELDS = {
    "last_name", "first_name", "business_name", "email",
    "phone_primary", "customer_type", "city", "state_province",
    "created_at",
}


@customers_bp.route("/")
@login_required
def list_customers():
    """List customers with pagination, search, and filtering."""
    form = CustomerSearchForm(request.args)
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "last_name")
    order = request.args.get("order", "asc")

    query = Customer.not_deleted()

    # Apply search filter
    if form.q.data:
        search_term = f"%{form.q.data}%"
        query = query.filter(
            db.or_(
                Customer.first_name.ilike(search_term),
                Customer.last_name.ilike(search_term),
                Customer.business_name.ilike(search_term),
                Customer.email.ilike(search_term),
                Customer.phone_primary.ilike(search_term),
            )
        )

    # Apply customer type filter
    if form.customer_type.data:
        query = query.filter_by(customer_type=form.customer_type.data)

    # Apply sorting -- validate against allowlist to prevent attribute injection
    if sort not in SORTABLE_FIELDS:
        sort = "last_name"
    sort_column = getattr(Customer, sort)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    pagination = query.paginate(page=page, per_page=25, error_out=False)

    return render_template(
        "customers/list.html",
        customers=pagination.items,
        pagination=pagination,
        form=form,
        sort=sort,
        order=order,
    )


@customers_bp.route("/<int:id>")
@login_required
def detail(id):
    """Display a single customer's detail page."""
    customer = db.session.get(Customer, id)
    if customer is None or customer.is_deleted:
        abort(404)
    return render_template("customers/detail.html", customer=customer)


@customers_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def create():
    """Show new customer form (GET) or create a customer (POST)."""
    form = CustomerForm()

    if form.validate_on_submit():
        customer = Customer(
            customer_type=form.customer_type.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            business_name=form.business_name.data,
            contact_person=form.contact_person.data,
            email=form.email.data,
            phone_primary=form.phone_primary.data,
            phone_secondary=form.phone_secondary.data,
            address_line1=form.address_line1.data,
            address_line2=form.address_line2.data,
            city=form.city.data,
            state_province=form.state_province.data,
            postal_code=form.postal_code.data,
            country=form.country.data,
            preferred_contact=form.preferred_contact.data,
            tax_exempt=form.tax_exempt.data,
            tax_id=form.tax_id.data,
            payment_terms=form.payment_terms.data,
            credit_limit=form.credit_limit.data,
            notes=form.notes.data,
            referral_source=form.referral_source.data,
            created_by=current_user.id,
        )
        db.session.add(customer)
        try:
            db.session.commit()
            flash("Customer created successfully.", "success")
            return redirect(url_for("customers.detail", id=customer.id))
        except IntegrityError:
            db.session.rollback()
            flash("A customer with that email already exists.", "error")

    return render_template("customers/form.html", form=form, is_edit=False)


@customers_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def edit(id):
    """Show edit customer form (GET) or update the customer (POST)."""
    customer = db.session.get(Customer, id)
    if customer is None or customer.is_deleted:
        abort(404)

    form = CustomerForm(obj=customer)

    if form.validate_on_submit():
        form.populate_obj(customer)
        try:
            db.session.commit()
            flash("Customer updated successfully.", "success")
            return redirect(url_for("customers.detail", id=customer.id))
        except IntegrityError:
            db.session.rollback()
            flash("A customer with that email already exists.", "error")

    return render_template(
        "customers/form.html", form=form, customer=customer, is_edit=True
    )


@customers_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
@roles_accepted("admin")
def delete(id):
    """Soft-delete a customer (admin only)."""
    customer = db.session.get(Customer, id)
    if customer is None or customer.is_deleted:
        abort(404)

    customer.soft_delete()
    db.session.commit()
    flash("Customer deleted.", "success")
    return redirect(url_for("customers.list_customers"))
