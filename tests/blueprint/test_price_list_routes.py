"""Blueprint tests for price list routes.

Tests listing, creating, viewing, editing, duplicating price list items
and managing categories.  Verifies role-based access control for
anonymous, viewer, technician, and admin users.

All write operations (create/edit/duplicate items and all category
management) require the 'admin' role.
"""

import pytest

from app.extensions import db
from app.models.price_list import PriceListCategory, PriceListItem


pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_category(db_session, **overrides):
    """Create and persist a PriceListCategory with sensible defaults."""
    defaults = dict(
        name="Regulator Service",
        description="Standard regulator services",
        sort_order=0,
        is_active=True,
    )
    defaults.update(overrides)
    category = PriceListCategory(**defaults)
    db.session.add(category)
    db.session.commit()
    return category


def _create_price_item(db_session, category_id=None, **overrides):
    """Create and persist a PriceListItem with sensible defaults."""
    if category_id is None:
        cat = _create_category(db_session)
        category_id = cat.id
    defaults = dict(
        category_id=category_id,
        name="Annual Service",
        code="REG-001",
        description="Full regulator annual service",
        price=85.00,
        cost=25.00,
        sort_order=0,
        is_active=True,
        is_taxable=True,
        is_per_unit=True,
        default_quantity=1,
        unit_label="each",
    )
    defaults.update(overrides)
    item = PriceListItem(**defaults)
    db.session.add(item)
    db.session.commit()
    return item


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------

class TestAnonymousAccess:
    """Anonymous users are redirected to the login page."""

    def test_list_redirects(self, client):
        response = client.get("/price-list/")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_detail_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = client.get(f"/price-list/{item_id}")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_get_redirects(self, client):
        response = client.get("/price-list/new")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_post_redirects(self, client):
        response = client.post("/price-list/new", data={"name": "X"})
        assert response.status_code == 302
        assert "/login" in response.location

    def test_edit_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = client.get(f"/price-list/{item_id}/edit")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_duplicate_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = client.post(f"/price-list/{item_id}/duplicate")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_categories_redirects(self, client):
        response = client.get("/price-list/categories")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_category_redirects(self, client):
        response = client.post(
            "/price-list/categories/new", data={"name": "X"}
        )
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Viewer role (read-only -- 403 on write operations)
# ---------------------------------------------------------------------------

class TestViewerAccess:
    """Viewer users can list/view but get 403 on create/edit/delete."""

    def test_list_returns_200(self, viewer_client, app, db_session):
        response = viewer_client.get("/price-list/")
        assert response.status_code == 200

    def test_detail_returns_200(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = viewer_client.get(f"/price-list/{item_id}")
        assert response.status_code == 200

    def test_create_get_forbidden(self, viewer_client):
        response = viewer_client.get("/price-list/new")
        assert response.status_code == 403

    def test_create_post_forbidden(self, viewer_client):
        response = viewer_client.post(
            "/price-list/new",
            data={"name": "Blocked", "price": "10.00"},
        )
        assert response.status_code == 403

    def test_edit_get_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = viewer_client.get(f"/price-list/{item_id}/edit")
        assert response.status_code == 403

    def test_edit_post_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = viewer_client.post(
            f"/price-list/{item_id}/edit",
            data={"name": "Nope"},
        )
        assert response.status_code == 403

    def test_duplicate_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = viewer_client.post(f"/price-list/{item_id}/duplicate")
        assert response.status_code == 403

    def test_categories_forbidden(self, viewer_client):
        """Categories page requires admin role, not just technician."""
        response = viewer_client.get("/price-list/categories")
        assert response.status_code == 403

    def test_create_category_forbidden(self, viewer_client):
        response = viewer_client.post(
            "/price-list/categories/new",
            data={"name": "Blocked Category"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Technician role (read-only -- all writes are admin-only)
# ---------------------------------------------------------------------------

class TestTechnicianAccess:
    """Technician users can list/view but get 403 on create/edit/duplicate."""

    def test_list_returns_200(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/price-list/")
        assert response.status_code == 200

    def test_list_shows_item(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_price_item(db_session, name="Visible Service")
        response = logged_in_client.get("/price-list/")
        assert response.status_code == 200
        assert b"Visible Service" in response.data

    def test_detail_returns_200(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = logged_in_client.get(f"/price-list/{item_id}")
        assert response.status_code == 200
        assert b"Annual Service" in response.data

    def test_detail_nonexistent_returns_404(self, logged_in_client):
        response = logged_in_client.get("/price-list/99999")
        assert response.status_code == 404

    # --- Write operations forbidden for technician (admin-only) ---

    def test_create_get_forbidden(self, logged_in_client):
        response = logged_in_client.get("/price-list/new")
        assert response.status_code == 403

    def test_create_post_forbidden(self, logged_in_client):
        response = logged_in_client.post(
            "/price-list/new",
            data={"name": "Blocked", "price": "10.00"},
        )
        assert response.status_code == 403

    def test_edit_get_forbidden(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = logged_in_client.get(f"/price-list/{item_id}/edit")
        assert response.status_code == 403

    def test_edit_post_forbidden(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = logged_in_client.post(
            f"/price-list/{item_id}/edit",
            data={"name": "Nope"},
        )
        assert response.status_code == 403

    def test_duplicate_forbidden(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = logged_in_client.post(f"/price-list/{item_id}/duplicate")
        assert response.status_code == 403

    def test_categories_forbidden(self, logged_in_client):
        response = logged_in_client.get("/price-list/categories")
        assert response.status_code == 403

    def test_create_category_forbidden(self, logged_in_client):
        response = logged_in_client.post(
            "/price-list/categories/new",
            data={"name": "Tech Category", "is_active": "y"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Admin role (full access including categories)
# ---------------------------------------------------------------------------

class TestAdminCRUD:
    """Admin users have full access including category management."""

    def test_list_returns_200(self, admin_client):
        response = admin_client.get("/price-list/")
        assert response.status_code == 200

    def test_create_post_works(self, admin_client, app, db_session):
        with app.app_context():
            cat = _create_category(db_session)
            cat_id = cat.id
        response = admin_client.post(
            "/price-list/new",
            data={
                "category_id": str(cat_id),
                "name": "Admin Service",
                "price": "120.00",
                "is_per_unit": "y",
                "default_quantity": "1",
                "unit_label": "each",
                "is_taxable": "y",
                "sort_order": "0",
                "is_active": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            item = PriceListItem.query.filter_by(name="Admin Service").first()
            assert item is not None

    def test_edit_post_works(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
            cat_id = item.category_id
        response = admin_client.post(
            f"/price-list/{item_id}/edit",
            data={
                "category_id": str(cat_id),
                "name": "Admin Edited",
                "code": "REG-001",
                "price": "99.00",
                "is_per_unit": "y",
                "default_quantity": "1",
                "unit_label": "each",
                "is_taxable": "y",
                "sort_order": "0",
                "is_active": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_create_post_invalid_rerenders_form(
        self, admin_client, app, db_session
    ):
        """Missing required price should fail validation."""
        with app.app_context():
            cat = _create_category(db_session)
            cat_id = cat.id
        response = admin_client.post(
            "/price-list/new",
            data={
                "category_id": str(cat_id),
                "name": "No Price",
                "price": "",  # Required
            },
            follow_redirects=False,
        )
        assert response.status_code == 200

    def test_edit_form_renders(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = admin_client.get(f"/price-list/{item_id}/edit")
        assert response.status_code == 200
        assert b"Annual Service" in response.data

    def test_edit_nonexistent_returns_404(self, admin_client):
        response = admin_client.get("/price-list/99999/edit")
        assert response.status_code == 404

    def test_duplicate_works(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_price_item(db_session)
            item_id = item.id
        response = admin_client.post(
            f"/price-list/{item_id}/duplicate", follow_redirects=False
        )
        assert response.status_code == 302

        with app.app_context():
            copy = PriceListItem.query.filter(
                PriceListItem.name.contains("(Copy)")
            ).first()
            assert copy is not None
            assert float(copy.price) == 85.00
            assert copy.code is None

    def test_duplicate_nonexistent_returns_404(self, admin_client):
        response = admin_client.post("/price-list/99999/duplicate")
        assert response.status_code == 404

    # --- Category management (admin has access) ---

    def test_categories_page_returns_200(self, admin_client, app, db_session):
        with app.app_context():
            _create_category(db_session)
        response = admin_client.get("/price-list/categories")
        assert response.status_code == 200
        assert b"Regulator Service" in response.data

    def test_create_category_works(self, admin_client, app, db_session):
        response = admin_client.post(
            "/price-list/categories/new",
            data={
                "name": "Drysuit Repairs",
                "description": "Drysuit repair services",
                "sort_order": "1",
                "is_active": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/price-list/categories" in response.location

        with app.app_context():
            cat = PriceListCategory.query.filter_by(name="Drysuit Repairs").first()
            assert cat is not None

    def test_edit_category_works(self, admin_client, app, db_session):
        with app.app_context():
            cat = _create_category(db_session)
            cat_id = cat.id
        response = admin_client.post(
            f"/price-list/categories/{cat_id}/edit",
            data={
                "name": "Updated Category",
                "sort_order": "5",
                "is_active": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/price-list/categories" in response.location

        with app.app_context():
            cat = db.session.get(PriceListCategory, cat_id)
            assert cat.name == "Updated Category"

    def test_edit_category_nonexistent_returns_404(self, admin_client):
        response = admin_client.post(
            "/price-list/categories/99999/edit",
            data={"name": "Nope"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestPriceListSearch:
    """Verify search query parameter on the list page."""

    def test_search_by_name(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_price_item(db_session, name="Searchable Service")
        response = logged_in_client.get("/price-list/?q=Searchable")
        assert response.status_code == 200
        assert b"Searchable Service" in response.data

    def test_search_by_code(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_price_item(db_session, code="UNIQUE-CODE")
        response = logged_in_client.get("/price-list/?q=UNIQUE-CODE")
        assert response.status_code == 200
        assert b"UNIQUE-CODE" in response.data
