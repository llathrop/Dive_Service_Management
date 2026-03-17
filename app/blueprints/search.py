"""Search blueprint.

Provides global search across customers, service items, inventory items,
service orders, and invoices.  Includes a full results page, an HTMX
autocomplete endpoint, and per-user saved search CRUD endpoints.
"""

import json

from flask import Blueprint, jsonify, render_template, request
from flask_security import current_user, login_required

from app.services import saved_search_service, search_service

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


# ── Saved Searches ────────────────────────────────────────────────────

@search_bp.route("/saved")
@login_required
def list_saved():
    """Return saved searches for the current user, optionally filtered by type.

    Query params:
        type: filter by search_type (customer, order, inventory, invoice)

    Returns JSON array of saved searches.
    """
    search_type = request.args.get("type")
    searches = saved_search_service.get_user_searches(
        current_user.id, search_type=search_type
    )
    return jsonify([
        {
            "id": s.id,
            "name": s.name,
            "search_type": s.search_type,
            "filters": s.filters,
            "is_default": s.is_default,
        }
        for s in searches
    ])


@search_bp.route("/saved", methods=["POST"])
@login_required
def create_saved():
    """Create a new saved search from JSON body.

    Expects JSON:
        name: string (required)
        search_type: string (required)
        filters: object (required)
        is_default: boolean (optional)
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required."}), 400

    name = (data.get("name") or "").strip()
    search_type = (data.get("search_type") or "").strip()
    filters = data.get("filters", {})
    is_default = bool(data.get("is_default", False))

    if not name:
        return jsonify({"error": "Name is required."}), 400
    if len(name) > 100:
        return jsonify({"error": "Name must be 100 characters or fewer."}), 400
    if not isinstance(filters, dict):
        return jsonify({"error": "Filters must be a JSON object."}), 400

    try:
        search = saved_search_service.create_search(
            user_id=current_user.id,
            name=name,
            search_type=search_type,
            filters=filters,
            is_default=is_default,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if search is None:
        return jsonify({"error": "A saved search with that name already exists."}), 409

    return jsonify({
        "id": search.id,
        "name": search.name,
        "search_type": search.search_type,
        "filters": search.filters,
        "is_default": search.is_default,
    }), 201


@search_bp.route("/saved/<int:id>", methods=["PUT"])
@login_required
def update_saved(id):
    """Update a saved search.

    Accepts partial updates — only provided fields are changed.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required."}), 400

    name = data.get("name")
    if name is not None:
        name = name.strip()
        if not name:
            return jsonify({"error": "Name cannot be empty."}), 400
        if len(name) > 100:
            return jsonify({"error": "Name must be 100 characters or fewer."}), 400

    filters = data.get("filters")
    if filters is not None and not isinstance(filters, dict):
        return jsonify({"error": "Filters must be a JSON object."}), 400

    is_default = data.get("is_default")
    if is_default is not None:
        is_default = bool(is_default)

    search = saved_search_service.update_search(
        search_id=id,
        user_id=current_user.id,
        name=name,
        filters=filters,
        is_default=is_default,
    )

    if search is None:
        return jsonify({"error": "Saved search not found."}), 404

    return jsonify({
        "id": search.id,
        "name": search.name,
        "search_type": search.search_type,
        "filters": search.filters,
        "is_default": search.is_default,
    })


@search_bp.route("/saved/<int:id>", methods=["DELETE"])
@login_required
def delete_saved(id):
    """Delete a saved search."""
    deleted = saved_search_service.delete_search(id, current_user.id)
    if not deleted:
        return jsonify({"error": "Saved search not found."}), 404
    return jsonify({"ok": True})


@search_bp.route("/saved/<int:id>/default", methods=["POST"])
@login_required
def set_default_saved(id):
    """Set a saved search as the default for its type."""
    search = saved_search_service.set_default(id, current_user.id)
    if search is None:
        return jsonify({"error": "Saved search not found."}), 404
    return jsonify({
        "id": search.id,
        "name": search.name,
        "is_default": search.is_default,
    })
