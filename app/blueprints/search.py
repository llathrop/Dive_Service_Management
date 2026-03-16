"""Search blueprint.

Provides global search across customers, service items, inventory items,
service orders, and invoices.  Includes a full results page and an HTMX
autocomplete endpoint that returns HTML fragments for the search bar
dropdown.
"""

from flask import Blueprint, render_template, request
from flask_security import login_required

from app.services import search_service

search_bp = Blueprint("search", __name__, url_prefix="/search")


@search_bp.route("/")
@login_required
def results():
    """Global search results page.

    Searches across customers, service items, inventory items, orders,
    and invoices using the ``q`` query parameter via the search service.
    """
    q = request.args.get("q", "").strip()

    search_results = search_service.global_search(q, limit=20)

    return render_template(
        "search/results.html",
        q=q,
        customers=search_results["customers"],
        items=search_results["service_items"],
        inventory=search_results["inventory_items"],
        orders=search_results["orders"],
        invoices=search_results["invoices"],
    )


@search_bp.route("/autocomplete")
@login_required
def autocomplete():
    """HTMX endpoint for search bar autocomplete.

    Returns an HTML fragment with grouped results (max 5 per category).
    Designed for debounced keyup triggers -- returns empty for queries
    shorter than 2 characters.
    """
    q = request.args.get("q", "").strip()

    search_results = search_service.global_search(q, limit=5)

    return render_template(
        "partials/search_autocomplete.html",
        q=q,
        customers=search_results["customers"],
        items=search_results["service_items"],
        inventory=search_results["inventory_items"],
        orders=search_results["orders"],
        invoices=search_results["invoices"],
    )
