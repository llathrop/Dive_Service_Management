"""Blueprint tests for customer routes.

Tests listing, creating, viewing, editing, and soft-deleting customer
records via the customers blueprint.  Verifies role-based access control
for anonymous, viewer, technician, and admin users.
"""

import pytest

from app.extensions import db
from app.models.customer import Customer


pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_customer(db_session, **overrides):
    """Create and persist a Customer with sensible defaults."""
    defaults = dict(
        customer_type="individual",
        first_name="Jane",
        last_name="Diver",
        email="jane@example.com",
        phone_primary="555-0100",
    )
    defaults.update(overrides)
    customer = Customer(**defaults)
    db.session.add(customer)
    db.session.commit()
    return customer


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------

class TestAnonymousAccess:
    """Anonymous users are redirected to the login page."""

    def test_list_redirects(self, client):
        response = client.get("/customers/")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_detail_redirects(self, client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = client.get(f"/customers/{cid}")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_get_redirects(self, client):
        response = client.get("/customers/new")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_post_redirects(self, client):
        response = client.post("/customers/new", data={"first_name": "X"})
        assert response.status_code == 302
        assert "/login" in response.location

    def test_edit_redirects(self, client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = client.get(f"/customers/{cid}/edit")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_delete_redirects(self, client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = client.post(f"/customers/{cid}/delete")
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Viewer role (read-only -- 403 on write operations)
# ---------------------------------------------------------------------------

class TestViewerAccess:
    """Viewer users can list/view but get 403 on create/edit/delete."""

    def test_list_returns_200(self, viewer_client, app, db_session):
        response = viewer_client.get("/customers/")
        assert response.status_code == 200

    def test_detail_returns_200(self, viewer_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = viewer_client.get(f"/customers/{cid}")
        assert response.status_code == 200

    def test_create_get_forbidden(self, viewer_client):
        response = viewer_client.get("/customers/new")
        assert response.status_code == 403

    def test_create_post_forbidden(self, viewer_client):
        response = viewer_client.post(
            "/customers/new",
            data={
                "customer_type": "individual",
                "first_name": "Blocked",
                "last_name": "User",
            },
        )
        assert response.status_code == 403

    def test_edit_get_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = viewer_client.get(f"/customers/{cid}/edit")
        assert response.status_code == 403

    def test_edit_post_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = viewer_client.post(
            f"/customers/{cid}/edit",
            data={"first_name": "Nope"},
        )
        assert response.status_code == 403

    def test_delete_forbidden(self, viewer_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = viewer_client.post(f"/customers/{cid}/delete")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Technician role (full CRUD)
# ---------------------------------------------------------------------------

class TestTechnicianCRUD:
    """Technician users can list, create, view, edit, and delete customers."""

    def test_list_returns_200(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/customers/")
        assert response.status_code == 200

    def test_list_shows_customer(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_customer(db_session, first_name="Visible", last_name="Customer")
        response = logged_in_client.get("/customers/")
        assert response.status_code == 200
        assert b"Visible" in response.data

    def test_list_hides_deleted_customer(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(
                db_session, first_name="Ghost", last_name="Customer"
            )
            customer.soft_delete()
            db.session.commit()
        response = logged_in_client.get("/customers/")
        assert response.status_code == 200
        assert b"Ghost" not in response.data

    def test_detail_returns_200(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = logged_in_client.get(f"/customers/{cid}")
        assert response.status_code == 200
        assert b"Jane" in response.data

    def test_detail_deleted_returns_404(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            customer.soft_delete()
            db.session.commit()
            cid = customer.id
        response = logged_in_client.get(f"/customers/{cid}")
        assert response.status_code == 404

    def test_detail_nonexistent_returns_404(self, logged_in_client):
        response = logged_in_client.get("/customers/99999")
        assert response.status_code == 404

    def test_create_form_renders(self, logged_in_client):
        response = logged_in_client.get("/customers/new")
        assert response.status_code == 200
        assert b"first_name" in response.data.lower() or b"First Name" in response.data

    def test_create_post_individual(self, logged_in_client, app, db_session):
        response = logged_in_client.post(
            "/customers/new",
            data={
                "customer_type": "individual",
                "first_name": "New",
                "last_name": "Customer",
                "email": "new@example.com",
                "preferred_contact": "email",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/customers/" in response.location

        with app.app_context():
            customer = Customer.query.filter_by(email="new@example.com").first()
            assert customer is not None
            assert customer.first_name == "New"
            assert customer.last_name == "Customer"

    def test_create_post_business(self, logged_in_client, app, db_session):
        response = logged_in_client.post(
            "/customers/new",
            data={
                "customer_type": "business",
                "business_name": "Dive Corp",
                "email": "info@divecorp.com",
                "preferred_contact": "email",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            customer = Customer.query.filter_by(business_name="Dive Corp").first()
            assert customer is not None

    def test_create_post_invalid_rerenders_form(self, logged_in_client):
        """Individual customer without last_name should fail validation."""
        response = logged_in_client.post(
            "/customers/new",
            data={
                "customer_type": "individual",
                "first_name": "Only",
                # Missing last_name
                "preferred_contact": "email",
            },
            follow_redirects=False,
        )
        # Should re-render form (200), not redirect (302)
        assert response.status_code == 200

    def test_edit_form_renders(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = logged_in_client.get(f"/customers/{cid}/edit")
        assert response.status_code == 200
        assert b"Jane" in response.data

    def test_edit_post_updates_customer(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = logged_in_client.post(
            f"/customers/{cid}/edit",
            data={
                "customer_type": "individual",
                "first_name": "Updated",
                "last_name": "Name",
                "preferred_contact": "email",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/customers/{cid}" in response.location

        with app.app_context():
            customer = db.session.get(Customer, cid)
            assert customer.first_name == "Updated"
            assert customer.last_name == "Name"

    def test_edit_deleted_returns_404(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            customer.soft_delete()
            db.session.commit()
            cid = customer.id
        response = logged_in_client.get(f"/customers/{cid}/edit")
        assert response.status_code == 404

    def test_delete_returns_403_for_technician(self, logged_in_client, app, db_session):
        """Technicians cannot delete customers (admin-only)."""
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = logged_in_client.post(f"/customers/{cid}/delete")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Admin role (same CRUD -- verify admin can also perform operations)
# ---------------------------------------------------------------------------

class TestAdminCRUD:
    """Admin users have full access to customer routes."""

    def test_list_returns_200(self, admin_client):
        response = admin_client.get("/customers/")
        assert response.status_code == 200

    def test_create_post_works(self, admin_client, app, db_session):
        response = admin_client.post(
            "/customers/new",
            data={
                "customer_type": "individual",
                "first_name": "Admin",
                "last_name": "Created",
                "preferred_contact": "email",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            customer = Customer.query.filter_by(first_name="Admin").first()
            assert customer is not None

    def test_edit_post_works(self, admin_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = admin_client.post(
            f"/customers/{cid}/edit",
            data={
                "customer_type": "individual",
                "first_name": "AdminEdit",
                "last_name": "Done",
                "preferred_contact": "email",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_delete_works(self, admin_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = admin_client.post(
            f"/customers/{cid}/delete", follow_redirects=False
        )
        assert response.status_code == 302

        with app.app_context():
            customer = db.session.get(Customer, cid)
            assert customer.is_deleted is True

    def test_delete_already_deleted_returns_404(self, admin_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            customer.soft_delete()
            db.session.commit()
            cid = customer.id
        response = admin_client.post(f"/customers/{cid}/delete")
        assert response.status_code == 404

    def test_delete_nonexistent_returns_404(self, admin_client):
        response = admin_client.post("/customers/99999/delete")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------

class TestCustomerSearch:
    """Verify search and filter query parameters on the list page."""

    def test_search_by_name(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_customer(db_session, first_name="Searchable", last_name="Diver")
        response = logged_in_client.get("/customers/?q=Searchable")
        assert response.status_code == 200
        assert b"Searchable" in response.data

    def test_filter_by_customer_type(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_customer(
                db_session,
                customer_type="business",
                business_name="Test Biz",
                first_name=None,
                last_name=None,
            )
        response = logged_in_client.get("/customers/?customer_type=business")
        assert response.status_code == 200
        assert b"Test Biz" in response.data

    def test_sort_order(self, logged_in_client, app, db_session):
        response = logged_in_client.get(
            "/customers/?sort=last_name&order=desc"
        )
        assert response.status_code == 200
