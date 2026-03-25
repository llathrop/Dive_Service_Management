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
from app.forms.portal import PortalInviteForm
from app.models.portal_user import PortalUser
from app.services import (
    audit_service,
    customer_service,
    email_service,
    portal_service,
    saved_search_service,
)

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
    portal_users = customer.portal_users.order_by(PortalUser.created_at.desc()).all()
    portal_invites = portal_service.get_customer_portal_invites(id)
    portal_invite_form = PortalInviteForm()
    if customer.email and not portal_invite_form.email.data:
        portal_invite_form.email.data = customer.email
    return render_template(
        "customers/detail.html",
        customer=customer,
        open_orders=open_orders,
        completed_orders=completed_orders,
        portal_users=portal_users,
        portal_invites=portal_invites,
        portal_invite_form=portal_invite_form,
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


@customers_bp.route("/<int:id>/portal-invite", methods=["POST"])
@login_required
@roles_accepted("admin")
def send_portal_invite(id):
    """Issue a portal invite for the customer from the detail page."""
    customer = customer_service.get_customer(id)
    form = PortalInviteForm()
    if not form.validate_on_submit():
        flash("Please provide a valid invite email address.", "error")
        return redirect(url_for("customers.detail", id=id))

    invite_email = form.email.data.strip() if form.email.data else ""
    try:
        token, raw_token = portal_service.create_portal_invite(
            customer.id,
            email=invite_email or customer.email,
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("customers.detail", id=id))

    invite_url = url_for("portal.activate", token=raw_token, _external=True)
    html_body = render_template(
        "email/portal_invite.html",
        customer=customer,
        invite_url=invite_url,
        token=token,
        inviter=current_user,
    )
    text_body = (
        f"Hello {customer.display_name},\n\n"
        f"Your customer portal invite is ready:\n{invite_url}\n\n"
        f"This link expires at {token.expires_at:%Y-%m-%d %H:%M UTC}.\n"
    )
    email_sent = email_service.send_email(
        token.email,
        f"Your portal invite for {customer.display_name}",
        html_body,
        text_body,
    )

    if email_sent:
        flash("Portal invite sent.", "success")
    else:
        flash(
            "Portal invite created, but email delivery is not currently configured.",
            "warning",
        )
    return redirect(url_for("customers.detail", id=id))


@customers_bp.route("/batch", methods=["POST"])
@login_required
@roles_accepted("admin")
def batch():
    """Apply a batch action to multiple customers."""
    selected_ids = request.form.getlist("selected_ids", type=int)
    action = request.form.get("action", "").strip()

    if not selected_ids:
        flash("No customers selected.", "warning")
        return redirect(url_for("customers.list_customers"))

    valid_actions = {"deactivate"}
    if action not in valid_actions:
        flash("Invalid batch action.", "error")
        return redirect(url_for("customers.list_customers"))

    success_count = 0
    error_count = 0

    for cid in selected_ids:
        try:
            customer = customer_service.get_customer(cid)
            old_deleted = customer.is_deleted
            customer.soft_delete()
            db.session.commit()
            try:
                audit_service.log_action(
                    action="delete",
                    entity_type="customer",
                    entity_id=customer.id,
                    user_id=current_user.id,
                    field_name="is_deleted",
                    old_value=str(old_deleted),
                    new_value=str(customer.is_deleted),
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
            success_count += 1
        except Exception:
            db.session.rollback()
            error_count += 1

    if success_count:
        flash(f"Batch {action}: {success_count} customer(s) updated.", "success")
    if error_count:
        flash(f"Batch {action}: {error_count} customer(s) could not be updated.", "warning")

    return redirect(url_for("customers.list_customers"))


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
