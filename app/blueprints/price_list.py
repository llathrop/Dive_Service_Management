"""Price List blueprint.

Provides routes for viewing and managing the shop's standard service
pricing.  The price list is organised into categories (accordion layout)
with individual priced items inside each.  Category management and price
changes require the 'admin' role.  All routes require authentication.
"""

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_security import current_user, login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.price_list import PriceListCategoryForm, PriceListItemForm
from app.models.price_list import PriceListCategory, PriceListItem
from app.services import audit_service

price_list_bp = Blueprint("price_list", __name__, url_prefix="/price-list")


def _populate_category_choices(form):
    """Set the category_id choices on a PriceListItemForm."""
    categories = (
        PriceListCategory.query
        .filter_by(is_active=True)
        .order_by(PriceListCategory.sort_order, PriceListCategory.name)
        .all()
    )
    form.category_id.choices = [(c.id, c.name) for c in categories]


@price_list_bp.route("/")
@login_required
def list_items():
    """Display the full price list in accordion layout by category."""
    q = request.args.get("q", "")

    categories = (
        PriceListCategory.query
        .filter_by(is_active=True)
        .order_by(PriceListCategory.sort_order, PriceListCategory.name)
        .all()
    )

    # Build a dict of category -> items
    category_items = {}
    for category in categories:
        items_query = (
            PriceListItem.query
            .filter_by(category_id=category.id, is_active=True)
            .order_by(PriceListItem.sort_order, PriceListItem.name)
        )
        if q:
            search_term = f"%{q}%"
            items_query = items_query.filter(
                db.or_(
                    PriceListItem.name.ilike(search_term),
                    PriceListItem.code.ilike(search_term),
                    PriceListItem.description.ilike(search_term),
                )
            )
        items = items_query.all()
        if items or not q:
            category_items[category] = items

    return render_template(
        "price_list/list.html",
        category_items=category_items,
        q=q,
    )


@price_list_bp.route("/pdf")
@login_required
def download_pdf():
    """Generate and download a customer-facing price list PDF."""
    categories = (
        PriceListCategory.query
        .filter_by(is_active=True)
        .order_by(PriceListCategory.sort_order, PriceListCategory.name)
        .all()
    )

    category_items = {}
    for category in categories:
        items = (
            PriceListItem.query
            .filter_by(category_id=category.id, is_active=True)
            .order_by(PriceListItem.sort_order, PriceListItem.name)
            .all()
        )
        if items:
            category_items[category] = items

    from app.utils.pdf import generate_price_list_pdf

    pdf_bytes = generate_price_list_pdf(category_items)

    inline = request.args.get("inline", "")
    filename = "price-list.pdf"
    if inline:
        disposition = f'inline; filename="{filename}"'
    else:
        disposition = f'attachment; filename="{filename}"'

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": disposition},
    )


@price_list_bp.route("/<int:id>")
@login_required
def detail(id):
    """Display price list item detail."""
    item = db.session.get(PriceListItem, id)
    if item is None:
        abort(404)
    return render_template("price_list/detail.html", item=item)


@price_list_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_accepted("admin")
def create():
    """Show new price list item form (GET) or create one (POST)."""
    form = PriceListItemForm()
    _populate_category_choices(form)

    if form.validate_on_submit():
        item = PriceListItem(
            category_id=form.category_id.data,
            code=form.code.data or None,
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            cost=form.cost.data,
            price_tier=form.price_tier.data,
            is_per_unit=form.is_per_unit.data,
            default_quantity=form.default_quantity.data,
            unit_label=form.unit_label.data,
            auto_deduct_parts=form.auto_deduct_parts.data,
            is_taxable=form.is_taxable.data,
            sort_order=form.sort_order.data or 0,
            is_active=form.is_active.data,
            internal_notes=form.internal_notes.data,
            updated_by=current_user.id,
        )
        db.session.add(item)
        try:
            db.session.commit()
            try:
                audit_service.log_action(
                    action="create",
                    entity_type="price_list_item",
                    entity_id=item.id,
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
            flash("Price list item created successfully.", "success")
            return redirect(url_for("price_list.detail", id=item.id))
        except IntegrityError:
            db.session.rollback()
            flash("A price list item with that code already exists.", "error")

    return render_template("price_list/form.html", form=form, is_edit=False)


@price_list_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@roles_accepted("admin")
def edit(id):
    """Show edit price list item form (GET) or update it (POST)."""
    item = db.session.get(PriceListItem, id)
    if item is None:
        abort(404)

    form = PriceListItemForm(obj=item)
    _populate_category_choices(form)

    if form.validate_on_submit():
        form.populate_obj(item)
        if not item.code:
            item.code = None
        item.updated_by = current_user.id
        try:
            db.session.commit()
            try:
                audit_service.log_action(
                    action="update",
                    entity_type="price_list_item",
                    entity_id=item.id,
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
            flash("Price list item updated successfully.", "success")
            return redirect(url_for("price_list.detail", id=item.id))
        except IntegrityError:
            db.session.rollback()
            flash("A price list item with that code already exists.", "error")

    return render_template(
        "price_list/form.html", form=form, item=item, is_edit=True
    )


@price_list_bp.route("/<int:id>/duplicate", methods=["POST"])
@login_required
@roles_accepted("admin")
def duplicate(id):
    """Duplicate a price list item."""
    original = db.session.get(PriceListItem, id)
    if original is None:
        abort(404)

    new_item = PriceListItem(
        category_id=original.category_id,
        code=None,  # Code must be unique; leave blank
        name=f"{original.name} (Copy)",
        description=original.description,
        price=original.price,
        cost=original.cost,
        price_tier=original.price_tier,
        is_per_unit=original.is_per_unit,
        default_quantity=original.default_quantity,
        unit_label=original.unit_label,
        auto_deduct_parts=original.auto_deduct_parts,
        is_taxable=original.is_taxable,
        sort_order=original.sort_order,
        is_active=True,
        internal_notes=original.internal_notes,
        updated_by=current_user.id,
    )
    db.session.add(new_item)
    try:
        db.session.commit()
        try:
            audit_service.log_action(
                action="create",
                entity_type="price_list_item",
                entity_id=new_item.id,
                user_id=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
                additional_data=f'{{"duplicated_from": {original.id}}}',
            )
        except Exception:
            pass
        flash("Price list item duplicated.", "success")
        return redirect(url_for("price_list.detail", id=new_item.id))
    except IntegrityError:
        db.session.rollback()
        flash("A price list item with that code already exists.", "error")
        return redirect(url_for("price_list.detail", id=original.id))


@price_list_bp.route("/categories")
@login_required
@roles_accepted("admin")
def categories():
    """Category management page (admin only)."""
    cats = (
        PriceListCategory.query
        .order_by(PriceListCategory.sort_order, PriceListCategory.name)
        .all()
    )
    form = PriceListCategoryForm()
    return render_template(
        "price_list/categories.html", categories=cats, form=form
    )


@price_list_bp.route("/categories/new", methods=["POST"])
@login_required
@roles_accepted("admin")
def create_category():
    """Create a new price list category."""
    form = PriceListCategoryForm()

    if form.validate_on_submit():
        category = PriceListCategory(
            name=form.name.data,
            description=form.description.data,
            sort_order=form.sort_order.data or 0,
            is_active=form.is_active.data,
        )
        db.session.add(category)
        db.session.commit()
        try:
            audit_service.log_action(
                action="create",
                entity_type="price_list_category",
                entity_id=category.id,
                user_id=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
        except Exception:
            pass
        flash("Category created successfully.", "success")
    else:
        flash("Invalid category data.", "error")

    return redirect(url_for("price_list.categories"))


@price_list_bp.route("/categories/<int:id>/edit", methods=["POST"])
@login_required
@roles_accepted("admin")
def edit_category(id):
    """Update an existing price list category."""
    category = db.session.get(PriceListCategory, id)
    if category is None:
        abort(404)

    form = PriceListCategoryForm(obj=category)

    if form.validate_on_submit():
        form.populate_obj(category)
        db.session.commit()
        try:
            audit_service.log_action(
                action="update",
                entity_type="price_list_category",
                entity_id=category.id,
                user_id=current_user.id,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
            )
        except Exception:
            pass
        flash("Category updated successfully.", "success")
    else:
        flash("Invalid category data.", "error")

    return redirect(url_for("price_list.categories"))
