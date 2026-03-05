"""Search blueprint.

Provides global search across customers, service items, and inventory
items.  Includes a full results page and an HTMX autocomplete endpoint
that returns HTML fragments for the search bar dropdown.
"""

from flask import Blueprint, render_template, request
from flask_security import login_required

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.service_item import ServiceItem

search_bp = Blueprint("search", __name__, url_prefix="/search")


@search_bp.route("/")
@login_required
def results():
    """Global search results page.

    Searches across customers, service items, and inventory items
    using the ``q`` query parameter.
    """
    q = request.args.get("q", "").strip()
    customers = []
    items = []
    inventory = []

    if q and len(q) >= 2:
        search_term = f"%{q}%"

        # Search customers
        customers = (
            Customer.not_deleted()
            .filter(
                db.or_(
                    Customer.first_name.ilike(search_term),
                    Customer.last_name.ilike(search_term),
                    Customer.business_name.ilike(search_term),
                    Customer.email.ilike(search_term),
                    Customer.phone_primary.ilike(search_term),
                )
            )
            .limit(20)
            .all()
        )

        # Search service items
        items = (
            ServiceItem.not_deleted()
            .filter(
                db.or_(
                    ServiceItem.name.ilike(search_term),
                    ServiceItem.serial_number.ilike(search_term),
                    ServiceItem.brand.ilike(search_term),
                )
            )
            .limit(20)
            .all()
        )

        # Search inventory items
        inventory = (
            InventoryItem.not_deleted()
            .filter(
                db.or_(
                    InventoryItem.name.ilike(search_term),
                    InventoryItem.sku.ilike(search_term),
                    InventoryItem.manufacturer.ilike(search_term),
                )
            )
            .limit(20)
            .all()
        )

    return render_template(
        "search/results.html",
        q=q,
        customers=customers,
        items=items,
        inventory=inventory,
    )


@search_bp.route("/autocomplete")
@login_required
def autocomplete():
    """HTMX endpoint for search bar autocomplete.

    Returns an HTML fragment with grouped results (max 5 per category).
    """
    q = request.args.get("q", "").strip()
    customers = []
    items = []
    inventory = []

    if q and len(q) >= 2:
        search_term = f"%{q}%"

        customers = (
            Customer.not_deleted()
            .filter(
                db.or_(
                    Customer.first_name.ilike(search_term),
                    Customer.last_name.ilike(search_term),
                    Customer.business_name.ilike(search_term),
                )
            )
            .limit(5)
            .all()
        )

        items = (
            ServiceItem.not_deleted()
            .filter(
                db.or_(
                    ServiceItem.name.ilike(search_term),
                    ServiceItem.serial_number.ilike(search_term),
                )
            )
            .limit(5)
            .all()
        )

        inventory = (
            InventoryItem.not_deleted()
            .filter(
                db.or_(
                    InventoryItem.name.ilike(search_term),
                    InventoryItem.sku.ilike(search_term),
                )
            )
            .limit(5)
            .all()
        )

    return render_template(
        "search/_autocomplete.html",
        q=q,
        customers=customers,
        items=items,
        inventory=inventory,
    )
