"""Blueprint tests for inventory routes.

Tests listing, creating, viewing, editing, soft-deleting, stock
adjustments, and the low-stock view for inventory items.  Verifies
role-based access control for anonymous, viewer, technician, and admin
users.
"""

import pytest

from app.extensions import db
from app.models.inventory import InventoryItem


pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_inventory_item(db_session, **overrides):
    """Create and persist an InventoryItem with sensible defaults."""
    defaults = dict(
        name="O-Ring Kit",
        category="Parts",
        sku="ORK-001",
        quantity_in_stock=50,
        reorder_level=10,
        unit_of_measure="each",
        is_active=True,
    )
    defaults.update(overrides)
    item = InventoryItem(**defaults)
    db.session.add(item)
    db.session.commit()
    return item


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------

class TestAnonymousAccess:
    """Anonymous users are redirected to the login page."""

    def test_list_redirects(self, client):
        response = client.get("/inventory/")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_detail_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = client.get(f"/inventory/{item_id}")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_get_redirects(self, client):
        response = client.get("/inventory/new")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_post_redirects(self, client):
        response = client.post("/inventory/new", data={"name": "X"})
        assert response.status_code == 302
        assert "/login" in response.location

    def test_edit_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = client.get(f"/inventory/{item_id}/edit")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_delete_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = client.post(f"/inventory/{item_id}/delete")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_adjust_stock_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = client.post(f"/inventory/{item_id}/adjust")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_low_stock_redirects(self, client):
        response = client.get("/inventory/low-stock")
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Viewer role (read-only -- 403 on write operations)
# ---------------------------------------------------------------------------

class TestViewerAccess:
    """Viewer users can list/view but get 403 on create/edit/delete/adjust."""

    def test_list_returns_200(self, viewer_client, app, db_session):
        response = viewer_client.get("/inventory/")
        assert response.status_code == 200

    def test_detail_returns_200(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = viewer_client.get(f"/inventory/{item_id}")
        assert response.status_code == 200

    def test_low_stock_returns_200(self, viewer_client):
        response = viewer_client.get("/inventory/low-stock")
        assert response.status_code == 200

    def test_create_get_forbidden(self, viewer_client):
        response = viewer_client.get("/inventory/new")
        assert response.status_code == 403

    def test_create_post_forbidden(self, viewer_client):
        response = viewer_client.post(
            "/inventory/new",
            data={"name": "Blocked", "category": "Parts"},
        )
        assert response.status_code == 403

    def test_edit_get_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = viewer_client.get(f"/inventory/{item_id}/edit")
        assert response.status_code == 403

    def test_edit_post_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = viewer_client.post(
            f"/inventory/{item_id}/edit",
            data={"name": "Nope"},
        )
        assert response.status_code == 403

    def test_delete_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = viewer_client.post(f"/inventory/{item_id}/delete")
        assert response.status_code == 403

    def test_adjust_stock_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = viewer_client.post(
            f"/inventory/{item_id}/adjust",
            data={"adjustment": 5, "reason": "Test"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Technician role (full CRUD)
# ---------------------------------------------------------------------------

class TestTechnicianCRUD:
    """Technician users can list, create, view, edit, delete, and adjust stock."""

    def test_list_returns_200(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/inventory/")
        assert response.status_code == 200

    def test_list_shows_item(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_inventory_item(db_session, name="Visible Part")
        response = logged_in_client.get("/inventory/")
        assert response.status_code == 200
        assert b"Visible Part" in response.data

    def test_list_hides_deleted_item(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session, name="Ghost Part")
            item.soft_delete()
            db.session.commit()
        response = logged_in_client.get("/inventory/")
        assert response.status_code == 200
        assert b"Ghost Part" not in response.data

    def test_detail_returns_200(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = logged_in_client.get(f"/inventory/{item_id}")
        assert response.status_code == 200
        assert b"O-Ring Kit" in response.data

    def test_detail_deleted_returns_404(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item.soft_delete()
            db.session.commit()
            item_id = item.id
        response = logged_in_client.get(f"/inventory/{item_id}")
        assert response.status_code == 404

    def test_detail_nonexistent_returns_404(self, logged_in_client):
        response = logged_in_client.get("/inventory/99999")
        assert response.status_code == 404

    def test_create_form_renders(self, logged_in_client):
        response = logged_in_client.get("/inventory/new")
        assert response.status_code == 200
        assert b"name" in response.data.lower()

    def test_create_post_works(self, logged_in_client, app, db_session):
        response = logged_in_client.post(
            "/inventory/new",
            data={
                "name": "New Seal",
                "category": "Seals",
                "sku": "SEAL-001",
                "quantity_in_stock": "20",
                "reorder_level": "5",
                "unit_of_measure": "each",
                "is_active": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/inventory/" in response.location

        with app.app_context():
            item = InventoryItem.query.filter_by(name="New Seal").first()
            assert item is not None
            assert item.category == "Seals"
            assert item.quantity_in_stock == 20

    def test_create_post_invalid_rerenders_form(self, logged_in_client):
        """Missing required category should fail validation."""
        response = logged_in_client.post(
            "/inventory/new",
            data={
                "name": "No Category",
                "category": "",  # Required
                "unit_of_measure": "each",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200

    def test_edit_form_renders(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = logged_in_client.get(f"/inventory/{item_id}/edit")
        assert response.status_code == 200
        assert b"O-Ring Kit" in response.data

    def test_edit_post_updates_item(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = logged_in_client.post(
            f"/inventory/{item_id}/edit",
            data={
                "name": "Updated O-Ring Kit",
                "category": "Parts",
                "sku": "ORK-001",
                "quantity_in_stock": "50",
                "reorder_level": "10",
                "unit_of_measure": "each",
                "is_active": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/inventory/{item_id}" in response.location

        with app.app_context():
            item = db.session.get(InventoryItem, item_id)
            assert item.name == "Updated O-Ring Kit"

    def test_edit_deleted_returns_404(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item.soft_delete()
            db.session.commit()
            item_id = item.id
        response = logged_in_client.get(f"/inventory/{item_id}/edit")
        assert response.status_code == 404

    def test_delete_returns_403_for_technician(self, logged_in_client, app, db_session):
        """Technicians cannot delete inventory items (admin-only)."""
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = logged_in_client.post(f"/inventory/{item_id}/delete")
        assert response.status_code == 403

    # --- Stock adjustment ---

    def test_adjust_stock_positive(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session, quantity_in_stock=10)
            item_id = item.id
        response = logged_in_client.post(
            f"/inventory/{item_id}/adjust",
            data={"adjustment": "5", "reason": "Restock"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/inventory/{item_id}" in response.location

        with app.app_context():
            item = db.session.get(InventoryItem, item_id)
            assert item.quantity_in_stock == 15

    def test_adjust_stock_negative(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session, quantity_in_stock=10)
            item_id = item.id
        response = logged_in_client.post(
            f"/inventory/{item_id}/adjust",
            data={"adjustment": "-3", "reason": "Used in service"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            item = db.session.get(InventoryItem, item_id)
            assert item.quantity_in_stock == 7

    def test_create_with_decimal_quantity(self, logged_in_client, app, db_session):
        """Decimal quantity_in_stock and reorder_level are accepted."""
        from decimal import Decimal
        response = logged_in_client.post(
            "/inventory/new",
            data={
                "name": "Neoprene Tape",
                "category": "Adhesives",
                "sku": "TAPE-001",
                "quantity_in_stock": "12.50",
                "reorder_level": "3.25",
                "unit_of_measure": "ft",
                "is_active": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            item = InventoryItem.query.filter_by(name="Neoprene Tape").first()
            assert item is not None
            assert item.quantity_in_stock == Decimal("12.50")
            assert item.reorder_level == Decimal("3.25")

    def test_adjust_stock_decimal(self, logged_in_client, app, db_session):
        """Decimal stock adjustments work correctly."""
        from decimal import Decimal
        with app.app_context():
            item = _create_inventory_item(
                db_session, quantity_in_stock=10, sku="DEC-ADJ-001"
            )
            item_id = item.id
        response = logged_in_client.post(
            f"/inventory/{item_id}/adjust",
            data={"adjustment": "2.5", "reason": "Partial restock"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            item = db.session.get(InventoryItem, item_id)
            assert item.quantity_in_stock == Decimal("12.50")

    def test_adjust_stock_negative_decimal(self, logged_in_client, app, db_session):
        """Negative decimal adjustments deduct fractional quantities."""
        from decimal import Decimal
        with app.app_context():
            item = _create_inventory_item(
                db_session, quantity_in_stock=10, sku="DEC-NEG-001"
            )
            item_id = item.id
        response = logged_in_client.post(
            f"/inventory/{item_id}/adjust",
            data={"adjustment": "-1.75", "reason": "Used partial"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            item = db.session.get(InventoryItem, item_id)
            assert item.quantity_in_stock == Decimal("8.25")

    def test_adjust_stock_deleted_returns_404(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item.soft_delete()
            db.session.commit()
            item_id = item.id
        response = logged_in_client.post(
            f"/inventory/{item_id}/adjust",
            data={"adjustment": "1", "reason": "Test"},
        )
        assert response.status_code == 404

    # --- Low stock view ---

    def test_low_stock_view_returns_200(self, logged_in_client):
        response = logged_in_client.get("/inventory/low-stock")
        assert response.status_code == 200

    def test_low_stock_view_shows_low_items(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_inventory_item(
                db_session,
                name="Low Stock Part",
                sku="LOW-001",
                quantity_in_stock=2,
                reorder_level=10,
                is_active=True,
            )
        response = logged_in_client.get("/inventory/low-stock")
        assert response.status_code == 200
        assert b"Low Stock Part" in response.data


# ---------------------------------------------------------------------------
# Admin role
# ---------------------------------------------------------------------------

class TestAdminCRUD:
    """Admin users have full access to inventory routes."""

    def test_list_returns_200(self, admin_client):
        response = admin_client.get("/inventory/")
        assert response.status_code == 200

    def test_create_post_works(self, admin_client, app, db_session):
        response = admin_client.post(
            "/inventory/new",
            data={
                "name": "Admin Part",
                "category": "Parts",
                "sku": "ADM-001",
                "quantity_in_stock": "10",
                "reorder_level": "2",
                "unit_of_measure": "each",
                "is_active": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            item = InventoryItem.query.filter_by(name="Admin Part").first()
            assert item is not None

    def test_edit_post_works(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = admin_client.post(
            f"/inventory/{item_id}/edit",
            data={
                "name": "AdminEdit Part",
                "category": "Parts",
                "sku": "ORK-001",
                "quantity_in_stock": "50",
                "reorder_level": "10",
                "unit_of_measure": "each",
                "is_active": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_delete_works(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item_id = item.id
        response = admin_client.post(
            f"/inventory/{item_id}/delete", follow_redirects=False
        )
        assert response.status_code == 302

        with app.app_context():
            item = db.session.get(InventoryItem, item_id)
            assert item.is_deleted is True

    def test_delete_already_deleted_returns_404(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session)
            item.soft_delete()
            db.session.commit()
            item_id = item.id
        response = admin_client.post(f"/inventory/{item_id}/delete")
        assert response.status_code == 404

    def test_delete_nonexistent_returns_404(self, admin_client):
        response = admin_client.post("/inventory/99999/delete")
        assert response.status_code == 404

    def test_adjust_stock_works(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_inventory_item(db_session, quantity_in_stock=20)
            item_id = item.id
        response = admin_client.post(
            f"/inventory/{item_id}/adjust",
            data={"adjustment": "10", "reason": "Admin restock"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            item = db.session.get(InventoryItem, item_id)
            assert item.quantity_in_stock == 30


# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------

class TestInventorySearch:
    """Verify search, filter, and sort query parameters on the list page."""

    def test_search_by_name(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_inventory_item(
                db_session, name="Findable Gasket", sku="FG-001"
            )
        response = logged_in_client.get("/inventory/?q=Findable")
        assert response.status_code == 200
        assert b"Findable Gasket" in response.data

    def test_search_by_sku(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_inventory_item(db_session, sku="UNIQUE-SKU-99")
        response = logged_in_client.get("/inventory/?q=UNIQUE-SKU-99")
        assert response.status_code == 200
        assert b"UNIQUE-SKU-99" in response.data

    def test_sort_order(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/inventory/?sort=name&order=desc")
        assert response.status_code == 200
