"""Saved search service layer — CRUD for per-user saved filters.

Provides functions for saving, loading, updating, and deleting saved
search configurations.  Enforces per-user uniqueness of search names
within a search type, and ensures at most one default per (user, type).
"""

import json

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.saved_search import VALID_SEARCH_TYPES, SavedSearch


def get_user_searches(user_id, search_type=None):
    """Return all saved searches for a user, optionally filtered by type.

    Results are ordered by name.
    """
    query = SavedSearch.query.filter_by(user_id=user_id)
    if search_type:
        query = query.filter_by(search_type=search_type)
    return query.order_by(SavedSearch.name).all()


def get_search(search_id, user_id):
    """Return a single saved search, ensuring it belongs to the user.

    Returns None if not found or not owned by the user.
    """
    return SavedSearch.query.filter_by(id=search_id, user_id=user_id).first()


def get_default_search(user_id, search_type):
    """Return the default saved search for a user + type, or None."""
    return SavedSearch.query.filter_by(
        user_id=user_id, search_type=search_type, is_default=True
    ).first()


def create_search(user_id, name, search_type, filters, is_default=False):
    """Create a new saved search.

    Args:
        user_id: Owner user ID.
        name: Display name for the saved search.
        search_type: One of VALID_SEARCH_TYPES.
        filters: Dict of filter criteria.
        is_default: Whether this should be the default for this type.

    Returns:
        The new SavedSearch, or None if name/type already exists for user.

    Raises:
        ValueError: If search_type is invalid.
    """
    if search_type not in VALID_SEARCH_TYPES:
        raise ValueError(f"Invalid search type: {search_type}")

    if is_default:
        _clear_default(user_id, search_type)

    search = SavedSearch(
        user_id=user_id,
        name=name.strip(),
        search_type=search_type,
        filters_json=json.dumps(filters),
        is_default=is_default,
    )
    db.session.add(search)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None
    return search


def update_search(search_id, user_id, name=None, filters=None, is_default=None):
    """Update an existing saved search.

    Only non-None arguments are updated.  Returns the updated search,
    or None if not found.
    """
    search = get_search(search_id, user_id)
    if search is None:
        return None

    if name is not None:
        search.name = name.strip()
    if filters is not None:
        search.filters_json = json.dumps(filters)
    if is_default is not None:
        if is_default:
            _clear_default(user_id, search.search_type)
        search.is_default = is_default

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None
    return search


def delete_search(search_id, user_id):
    """Delete a saved search.  Returns True if deleted, False if not found."""
    search = get_search(search_id, user_id)
    if search is None:
        return False
    db.session.delete(search)
    db.session.commit()
    return True


def set_default(search_id, user_id):
    """Set a saved search as the default for its type.

    Clears the existing default (if any) for the same (user, type).
    Returns the updated search, or None if not found.
    """
    search = get_search(search_id, user_id)
    if search is None:
        return None
    _clear_default(user_id, search.search_type)
    search.is_default = True
    db.session.commit()
    return search


def _clear_default(user_id, search_type):
    """Clear any existing default for a (user, search_type) pair."""
    SavedSearch.query.filter_by(
        user_id=user_id, search_type=search_type, is_default=True
    ).update({"is_default": False})
