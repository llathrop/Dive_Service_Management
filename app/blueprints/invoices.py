"""Invoices blueprint.

Provides routes for the full billing workflow: listing, creating,
viewing, editing, and voiding invoices, as well as managing invoice
line items and recording payments.  Supports generating invoices from
service orders.  All routes require authentication.  Write operations
require the 'admin' or 'technician' role; voiding requires 'admin'.

Phase 4 blueprints delegate all business logic to the service layer
(``app.services.invoice_service``) instead of performing direct DB
operations.
"""

from flask import (
    Blueprint,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_security import current_user, login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.invoice import (
    InvoiceForm,
    InvoiceLineItemForm,
    InvoiceSearchForm,
    PaymentForm,
)
from app.models.customer import Customer
from app.services import invoice_service

invoices_bp = Blueprint("invoices", __name__, url_prefix="/invoices")

# Columns that the list view is allowed to sort by.
SORTABLE_FIELDS = {
    "invoice_number",
    "status",
    "issue_date",
    "due_date",
    "total",
    "balance_due",
    "created_at",
}


# ======================================================================
# Helper functions
# ======================================================================


def _populate_invoice_form_choices(form):
    """Populate dynamic choices on an InvoiceForm.

    Sets customer_id choices from non-deleted customers.
    """
    customers = (
        Customer.not_deleted()
        .order_by(Customer.last_name, Customer.first_name)
        .all()
    )
    form.customer_id.choices = [
        ("", "-- Select --"),
        ("__new__", "+ Create New Customer"),
    ] + [
        (c.id, c.display_name) for c in customers
    ]


# ======================================================================
# Routes -- Invoice CRUD
# ======================================================================


@invoices_bp.route("/")
@login_required
def list_invoices():
    """List invoices with pagination, search, and filtering."""
    form = InvoiceSearchForm(request.args)

    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "issue_date")
    order = request.args.get("order", "desc")

    # Validate sort field against allowlist
    if sort not in SORTABLE_FIELDS:
        sort = "issue_date"

    pagination = invoice_service.get_invoices(
        page=page,
        per_page=25,
        search=form.q.data,
        status=form.status.data,
        date_from=form.date_from.data,
        date_to=form.date_to.data,
        overdue_only=form.overdue_only.data,
        sort=sort,
        order=order,
    )

    return render_template(
        "invoices/list.html",
        invoices=pagination,
        form=form,
        sort=sort,
        order=order,
    )


@invoices_bp.route("/<int:id>")
@login_required
def detail(id):
    """Display an invoice detail page with line items and payments."""
    invoice = invoice_service.get_invoice(id)
    if invoice is None:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.list_invoices"))

    payments = invoice_service.get_payments(id)

    # Create sub-forms for the detail page
    line_item_form = InvoiceLineItemForm()
    payment_form = PaymentForm()

    return render_template(
        "invoices/detail.html",
        invoice=invoice,
        payments=payments,
        line_item_form=line_item_form,
        payment_form=payment_form,
    )


@invoices_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def create():
    """Show new invoice form (GET) or create an invoice (POST)."""
    form = InvoiceForm()
    _populate_invoice_form_choices(form)

    if form.validate_on_submit():
        data = {
            "customer_id": form.customer_id.data,
            "status": form.status.data,
            "issue_date": form.issue_date.data,
            "due_date": form.due_date.data,
            "tax_rate": form.tax_rate.data,
            "discount_amount": form.discount_amount.data,
            "notes": form.notes.data,
            "customer_notes": form.customer_notes.data,
            "terms": form.terms.data,
        }
        try:
            new_invoice = invoice_service.create_invoice(
                data, created_by=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
            flash("Invoice created successfully.", "success")
            return redirect(url_for("invoices.detail", id=new_invoice.id))
        except IntegrityError:
            db.session.rollback()
            flash(
                "An invoice with that number already exists.",
                "error",
            )

    return render_template("invoices/form.html", form=form, is_edit=False)


@invoices_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def edit(id):
    """Show edit invoice form (GET) or update the invoice (POST)."""
    invoice = invoice_service.get_invoice(id)
    if invoice is None:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.list_invoices"))

    form = InvoiceForm(obj=invoice)
    _populate_invoice_form_choices(form)

    if form.validate_on_submit():
        data = {
            "customer_id": form.customer_id.data,
            "issue_date": form.issue_date.data,
            "due_date": form.due_date.data,
            "tax_rate": form.tax_rate.data,
            "discount_amount": form.discount_amount.data,
            "notes": form.notes.data,
            "customer_notes": form.customer_notes.data,
            "terms": form.terms.data,
        }
        try:
            invoice_service.update_invoice(
                id, data,
                user_id=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
            flash("Invoice updated successfully.", "success")
            return redirect(url_for("invoices.detail", id=id))
        except IntegrityError:
            db.session.rollback()
            flash(
                "An error occurred while updating the invoice.",
                "error",
            )

    return render_template(
        "invoices/form.html", form=form, invoice=invoice, is_edit=True
    )


# ======================================================================
# Routes -- Void & Status
# ======================================================================


@invoices_bp.route("/<int:id>/void", methods=["POST"])
@login_required
@roles_accepted("admin")
def void_invoice(id):
    """Void an invoice (admin only)."""
    invoice = invoice_service.void_invoice(
        id,
        user_id=current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )
    if invoice is None:
        flash("Invoice not found.", "error")
    else:
        flash(
            f"Invoice {invoice.invoice_number} has been voided.",
            "success",
        )
    return redirect(url_for("invoices.detail", id=id))


@invoices_bp.route("/<int:id>/status", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def change_status(id):
    """Change the status of an invoice using validated transitions."""
    new_status = request.form.get("new_status", "").strip()
    if not new_status:
        flash("No status provided.", "error")
        return redirect(url_for("invoices.detail", id=id))

    invoice, success = invoice_service.change_status(
        id, new_status,
        user_id=current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )
    if invoice is None:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoices.list_invoices"))

    if not success:
        flash(
            f"Cannot change status from "
            f"'{invoice.display_status}' to "
            f"'{new_status.replace('_', ' ').title()}'.",
            "error",
        )
    else:
        flash(
            f"Invoice status changed to {invoice.display_status}.",
            "success",
        )
    return redirect(url_for("invoices.detail", id=id))


# ======================================================================
# Routes -- Line Items
# ======================================================================


@invoices_bp.route("/<int:id>/line-items/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_line_item(id):
    """Add a line item to an invoice."""
    form = InvoiceLineItemForm()

    if form.validate_on_submit():
        data = {
            "line_type": form.line_type.data,
            "description": form.description.data,
            "quantity": form.quantity.data,
            "unit_price": form.unit_price.data,
        }
        try:
            result = invoice_service.add_line_item(id, data)
            if result is None:
                flash("Invoice not found.", "error")
            else:
                flash("Line item added.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    return redirect(url_for("invoices.detail", id=id))


@invoices_bp.route("/line-items/<int:item_id>/remove", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def remove_line_item(item_id):
    """Remove a line item from an invoice."""
    from app.models.invoice import InvoiceLineItem

    line_item = db.session.get(InvoiceLineItem, item_id)
    if line_item is None:
        flash("Line item not found.", "error")
        return redirect(url_for("invoices.list_invoices"))

    invoice_id = line_item.invoice_id
    invoice_service.remove_line_item(item_id)
    flash("Line item removed.", "success")
    return redirect(url_for("invoices.detail", id=invoice_id))


# ======================================================================
# Routes -- Payments
# ======================================================================


@invoices_bp.route("/<int:id>/payments/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_payment(id):
    """Record a payment against an invoice."""
    form = PaymentForm()

    if form.validate_on_submit():
        data = {
            "payment_type": form.payment_type.data,
            "amount": form.amount.data,
            "payment_date": form.payment_date.data,
            "payment_method": form.payment_method.data,
            "reference_number": form.reference_number.data,
            "notes": form.notes.data,
        }
        result = invoice_service.record_payment(
            id, data, recorded_by=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
        if result is None:
            flash("Invoice not found.", "error")
        else:
            flash("Payment recorded.", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    return redirect(url_for("invoices.detail", id=id))


# ======================================================================
# Routes -- PDF Download
# ======================================================================


@invoices_bp.route("/<int:id>/pdf")
@login_required
@roles_accepted("admin", "technician")
def download_pdf(id):
    """Generate and download the invoice as a PDF.

    Supports an optional ``?inline=1`` query parameter to display the
    PDF in the browser rather than downloading it.
    """
    from flask import abort

    invoice = invoice_service.get_invoice(id)
    if invoice is None:
        abort(404)

    from app.utils.pdf import generate_invoice_pdf

    pdf_bytes = generate_invoice_pdf(invoice)
    filename = f"{invoice.invoice_number}.pdf"

    inline = request.args.get("inline", "")
    if inline:
        disposition = f'inline; filename="{filename}"'
    else:
        disposition = f'attachment; filename="{filename}"'

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": disposition},
    )


# ======================================================================
# Routes -- Generate from Order
# ======================================================================


@invoices_bp.route(
    "/from-order/<int:order_id>/generate", methods=["POST"]
)
@login_required
@roles_accepted("admin", "technician")
def generate_from_order(order_id):
    """Generate an invoice from a service order."""
    try:
        invoice = invoice_service.generate_from_order(
            order_id, created_by=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
        flash(
            f"Invoice {invoice.invoice_number} generated from order.",
            "success",
        )
        return redirect(url_for("invoices.detail", id=invoice.id))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("orders.detail", id=order_id))


@invoices_bp.route(
    "/from-order/<int:order_id>/preview", methods=["GET"]
)
@login_required
def cost_preview(order_id):
    """Return a JSON cost preview for generating an invoice from an order."""
    try:
        preview = invoice_service.get_order_cost_preview(order_id)
        return jsonify(preview)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
