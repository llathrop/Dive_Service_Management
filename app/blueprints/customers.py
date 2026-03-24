"""Customers blueprint.

Provides routes for listing, creating, viewing, editing, and soft-deleting
customer records.  All routes require authentication.  Write operations
(create, edit, delete) require the 'admin' or 'technician' role.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_security import current_user, login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.customer import CustomerForm, CustomerSearchForm
from app.services import audit_service, customer_service, saved_search_service

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
    # Apply default saved search when no filter params are provided
    filter_keys = ["q", "customer_type", "sort", "order"]
    if not any(request.args.get(k) for k in filter_keys):
        try:
            default_search = saved_search_service.get_default_search(
                user_id=current_user.id, search_type="customer"
            )
            if default_search:
                filters = default_search.filters
                from werkzeug.datastructures import ImmutableMultiDict
                args = ImmutableMultiDict(filters)
                form = CustomerSearchForm(args)
                page = int(filters.get("page", 1))
                sort = filters.get("sort", "last_name")
                order = filters.get("order", "asc")
            else:
                form = CustomerSearchForm(request.args)
                page = request.args.get("page", 1, type=int)
                sort = request.args.get("sort", "last_name")
                order = request.args.get("order", "asc")
        except Exception:
            form = CustomerSearchForm(request.args)
            page = request.args.get("page", 1, type=int)
            sort = request.args.get("sort", "last_name")
            order = request.args.get("order", "asc")
    else:
        form = CustomerSearchForm(request.args)
        page = request.args.get("page", 1, type=int)
        sort = request.args.get("sort", "last_name")
        order = request.args.get("order", "asc")

    # Validate sort against allowlist to prevent attribute injection
    if sort not in SORTABLE_FIELDS:
        sort = "last_name"

    pagination = customer_service.get_customers(
        page=page,
        per_page=25,
        search=form.q.data,
        customer_type=form.customer_type.data,
        sort=sort,
        order=order,
    )

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
    customer = customer_service.get_customer(id)
    open_orders = customer_service.get_customer_orders(id, active_only=True)
    completed_orders = customer_service.get_customer_orders(id, active_only=False)
    return render_template(
        "customers/detail.html",
        customer=customer,
        open_orders=open_orders,
        completed_orders=completed_orders,
    )


@customers_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def create():
    """Show new customer form (GET) or create a customer (POST)."""
    form = CustomerForm()

    if form.validate_on_submit():
        data = {
            "customer_type": form.customer_type.data,
            "first_name": form.first_name.data,
            "last_name": form.last_name.data,
            "business_name": form.business_name.data,
            "contact_person": form.contact_person.data,
            "email": form.email.data,
            "phone_primary": form.phone_primary.data,
            "phone_secondary": form.phone_secondary.data,
            "address_line1": form.address_line1.data,
            "address_line2": form.address_line2.data,
            "city": form.city.data,
            "state_province": form.state_province.data,
            "postal_code": form.postal_code.data,
            "country": form.country.data,
            "preferred_contact": form.preferred_contact.data,
            "tax_exempt": form.tax_exempt.data,
            "tax_id": form.tax_id.data,
            "payment_terms": form.payment_terms.data,
            "credit_limit": form.credit_limit.data,
            "notes": form.notes.data,
            "referral_source": form.referral_source.data,
        }
        try:
            customer = customer_service.create_customer(
                data, created_by=current_user.id
            )
            try:
                audit_service.log_action(
                    action="create",
                    entity_type="customer",
                    entity_id=customer.id,
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
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
    customer = customer_service.get_customer(id)

    form = CustomerForm(obj=customer)

    if form.validate_on_submit():
        data = {
            "customer_type": form.customer_type.data,
            "first_name": form.first_name.data,
            "last_name": form.last_name.data,
            "business_name": form.business_name.data,
            "contact_person": form.contact_person.data,
            "email": form.email.data,
            "phone_primary": form.phone_primary.data,
            "phone_secondary": form.phone_secondary.data,
            "address_line1": form.address_line1.data,
            "address_line2": form.address_line2.data,
            "city": form.city.data,
            "state_province": form.state_province.data,
            "postal_code": form.postal_code.data,
            "country": form.country.data,
            "preferred_contact": form.preferred_contact.data,
            "tax_exempt": form.tax_exempt.data,
            "tax_id": form.tax_id.data,
            "payment_terms": form.payment_terms.data,
            "credit_limit": form.credit_limit.data,
            "notes": form.notes.data,
            "referral_source": form.referral_source.data,
        }
        try:
            customer = customer_service.update_customer(id, data)
            try:
                audit_service.log_action(
                    action="update",
                    entity_type="customer",
                    entity_id=customer.id,
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
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
    customer = customer_service.delete_customer(id)
    try:
        audit_service.log_action(
            action="delete",
            entity_type="customer",
            entity_id=customer.id,
            user_id=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except Exception:
        pass
    flash("Customer deleted.", "success")
    return redirect(url_for("customers.list_customers"))
