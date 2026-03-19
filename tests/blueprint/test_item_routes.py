"""Blueprint tests for service item routes.

Tests listing, creating, viewing, editing, soft-deleting, and serial
number lookup for service items.  Verifies role-based access control
for anonymous, viewer, technician, and admin users.
"""

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.service_item import ServiceItem


pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_customer(db_session):
    """Create a minimal customer for FK references."""
    customer = Customer(
        customer_type="individual",
        first_name="Owner",
        last_name="Person",
    )
    db.session.add(customer)
    db.session.commit()
    return customer


def _create_item(db_session, customer_id=None, **overrides):
    """Create and persist a ServiceItem with sensible defaults."""
    if customer_id is None:
        customer_id = _create_customer(db_session).id
    defaults = dict(
        name="Test Regulator",
        item_category="Regulator",
        serial_number="SN-12345",
        brand="Apeks",
        model="XTX50",
        serviceability="serviceable",
        customer_id=customer_id,
    )
    defaults.update(overrides)
    item = ServiceItem(**defaults)
    db.session.add(item)
    db.session.commit()
    return item


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------

class TestAnonymousAccess:
    """Anonymous users are redirected to the login page."""

    def test_list_redirects(self, client):
        response = client.get("/items/")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_detail_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = client.get(f"/items/{item_id}")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_get_redirects(self, client):
        response = client.get("/items/new")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_post_redirects(self, client):
        response = client.post("/items/new", data={"name": "X"})
        assert response.status_code == 302
        assert "/login" in response.location

    def test_edit_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = client.get(f"/items/{item_id}/edit")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_delete_redirects(self, client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = client.post(f"/items/{item_id}/delete")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_lookup_redirects(self, client):
        response = client.get("/items/lookup")
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Viewer role (read-only -- 403 on write operations)
# ---------------------------------------------------------------------------

class TestViewerAccess:
    """Viewer users can list/view but get 403 on create/edit/delete."""

    def test_list_returns_200(self, viewer_client, app, db_session):
        response = viewer_client.get("/items/")
        assert response.status_code == 200

    def test_detail_returns_200(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = viewer_client.get(f"/items/{item_id}")
        assert response.status_code == 200

    def test_lookup_returns_200(self, viewer_client):
        response = viewer_client.get("/items/lookup")
        assert response.status_code == 200

    def test_create_get_forbidden(self, viewer_client):
        response = viewer_client.get("/items/new")
        assert response.status_code == 403

    def test_create_post_forbidden(self, viewer_client):
        response = viewer_client.post(
            "/items/new",
            data={"name": "Blocked", "item_category": "BCD"},
        )
        assert response.status_code == 403

    def test_edit_get_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = viewer_client.get(f"/items/{item_id}/edit")
        assert response.status_code == 403

    def test_edit_post_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = viewer_client.post(
            f"/items/{item_id}/edit",
            data={"name": "Nope"},
        )
        assert response.status_code == 403

    def test_delete_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = viewer_client.post(f"/items/{item_id}/delete")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Technician role (full CRUD)
# ---------------------------------------------------------------------------

class TestTechnicianCRUD:
    """Technician users can list, create, view, edit, and delete items."""

    def test_list_returns_200(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/items/")
        assert response.status_code == 200

    def test_list_shows_item(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_item(db_session, name="Visible Reg")
        response = logged_in_client.get("/items/")
        assert response.status_code == 200
        assert b"Visible Reg" in response.data

    def test_list_hides_deleted_item(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session, name="Ghost Item")
            item.soft_delete()
            db.session.commit()
        response = logged_in_client.get("/items/")
        assert response.status_code == 200
        assert b"Ghost Item" not in response.data

    def test_detail_returns_200(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = logged_in_client.get(f"/items/{item_id}")
        assert response.status_code == 200
        assert b"Test Regulator" in response.data

    def test_detail_deleted_returns_404(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item.soft_delete()
            db.session.commit()
            item_id = item.id
        response = logged_in_client.get(f"/items/{item_id}")
        assert response.status_code == 404

    def test_detail_nonexistent_returns_404(self, logged_in_client):
        response = logged_in_client.get("/items/99999")
        assert response.status_code == 404

    def test_create_form_renders(self, logged_in_client):
        response = logged_in_client.get("/items/new")
        assert response.status_code == 200
        assert b"name" in response.data.lower()

    def test_create_post_works(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cust_id = customer.id
        response = logged_in_client.post(
            "/items/new",
            data={
                "name": "New BCD",
                "item_category": "BCD",
                "serviceability": "serviceable",
                "serial_number": "SN-NEW-001",
                "customer_id": str(cust_id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/items/" in response.location

        with app.app_context():
            item = ServiceItem.query.filter_by(name="New BCD").first()
            assert item is not None
            assert item.item_category == "BCD"

    def test_create_post_with_customer(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cust_id = customer.id
        response = logged_in_client.post(
            "/items/new",
            data={
                "name": "Customer BCD",
                "item_category": "BCD",
                "serviceability": "serviceable",
                "customer_id": str(cust_id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            item = ServiceItem.query.filter_by(name="Customer BCD").first()
            assert item is not None
            assert item.customer_id == cust_id

    def test_create_post_invalid_rerenders_form(self, logged_in_client):
        """Missing required name field should fail validation."""
        response = logged_in_client.post(
            "/items/new",
            data={
                "name": "",  # Required field empty
                "item_category": "BCD",
                "serviceability": "serviceable",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200

    def test_edit_form_renders(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = logged_in_client.get(f"/items/{item_id}/edit")
        assert response.status_code == 200
        assert b"Test Regulator" in response.data

    def test_edit_post_updates_item(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
            cust_id = item.customer_id
        response = logged_in_client.post(
            f"/items/{item_id}/edit",
            data={
                "name": "Updated Reg",
                "item_category": "Regulator",
                "serviceability": "serviceable",
                "serial_number": "SN-12345",
                "customer_id": str(cust_id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/items/{item_id}" in response.location

        with app.app_context():
            item = db.session.get(ServiceItem, item_id)
            assert item.name == "Updated Reg"

    def test_edit_deleted_returns_404(self, logged_in_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item.soft_delete()
            db.session.commit()
            item_id = item.id
        response = logged_in_client.get(f"/items/{item_id}/edit")
        assert response.status_code == 404

    def test_delete_returns_403_for_technician(self, logged_in_client, app, db_session):
        """Technicians cannot delete items (admin-only)."""
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = logged_in_client.post(f"/items/{item_id}/delete")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Admin role
# ---------------------------------------------------------------------------

class TestAdminCRUD:
    """Admin users have full access to service item routes."""

    def test_list_returns_200(self, admin_client):
        response = admin_client.get("/items/")
        assert response.status_code == 200

    def test_create_post_works(self, admin_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cust_id = customer.id
        response = admin_client.post(
            "/items/new",
            data={
                "name": "Admin BCD",
                "item_category": "BCD",
                "serviceability": "serviceable",
                "serial_number": "SN-ADM-001",
                "customer_id": str(cust_id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            item = ServiceItem.query.filter_by(name="Admin BCD").first()
            assert item is not None

    def test_edit_post_works(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
            cust_id = item.customer_id
        response = admin_client.post(
            f"/items/{item_id}/edit",
            data={
                "name": "AdminEdit",
                "item_category": "Regulator",
                "serviceability": "serviceable",
                "serial_number": "SN-12345",
                "customer_id": str(cust_id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_delete_works(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item_id = item.id
        response = admin_client.post(
            f"/items/{item_id}/delete", follow_redirects=False
        )
        assert response.status_code == 302

        with app.app_context():
            item = db.session.get(ServiceItem, item_id)
            assert item.is_deleted is True

    def test_delete_already_deleted_returns_404(self, admin_client, app, db_session):
        with app.app_context():
            item = _create_item(db_session)
            item.soft_delete()
            db.session.commit()
            item_id = item.id
        response = admin_client.post(f"/items/{item_id}/delete")
        assert response.status_code == 404

    def test_delete_nonexistent_returns_404(self, admin_client):
        response = admin_client.post("/items/99999/delete")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Serial number lookup
# ---------------------------------------------------------------------------

class TestLookup:
    """Verify the serial number lookup page works."""

    def test_lookup_page_renders(self, logged_in_client):
        response = logged_in_client.get("/items/lookup")
        assert response.status_code == 200

    def test_lookup_finds_item(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_item(db_session, serial_number="LOOKUP-001")
        response = logged_in_client.get("/items/lookup?serial=LOOKUP-001")
        assert response.status_code == 200
        assert b"LOOKUP-001" in response.data

    def test_lookup_no_match(self, logged_in_client):
        response = logged_in_client.get("/items/lookup?serial=NONEXISTENT")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------

class TestItemSearch:
    """Verify search and sort query parameters on the list page."""

    def test_search_by_name(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_item(db_session, name="Findable Reg", serial_number="SN-FIND")
        response = logged_in_client.get("/items/?q=Findable")
        assert response.status_code == 200
        assert b"Findable Reg" in response.data

    def test_search_by_serial(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_item(db_session, serial_number="SN-UNIQUE-99")
        response = logged_in_client.get("/items/?q=SN-UNIQUE-99")
        assert response.status_code == 200
        assert b"SN-UNIQUE-99" in response.data

    def test_sort_order(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/items/?sort=name&order=desc")
        assert response.status_code == 200
