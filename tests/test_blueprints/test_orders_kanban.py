"""Tests for the Kanban board view and status change endpoint."""

import pytest

from tests.factories import CustomerFactory, ServiceOrderFactory

pytestmark = pytest.mark.blueprint


KANBAN_URL = "/orders/kanban"


def _kanban_status_url(order_id):
    return f"/orders/{order_id}/kanban-status"


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    """Bind Factory Boy factories to the test database session."""
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session


class TestKanbanPageAccess:
    """Authentication and authorization for the kanban page."""

    def test_kanban_requires_authentication(self, client):
        """Unauthenticated users are redirected to login."""
        resp = client.get(KANBAN_URL)
        assert resp.status_code == 302
        assert "/login" in resp.location

    def test_kanban_requires_admin_or_tech_role(self, viewer_client):
        """Viewer role gets 403 on the kanban page."""
        resp = viewer_client.get(KANBAN_URL)
        assert resp.status_code == 403

    def test_kanban_accessible_by_technician(self, logged_in_client):
        """Technician role can access the kanban board."""
        resp = logged_in_client.get(KANBAN_URL)
        assert resp.status_code == 200

    def test_kanban_accessible_by_admin(self, admin_client):
        """Admin role can access the kanban board."""
        resp = admin_client.get(KANBAN_URL)
        assert resp.status_code == 200


class TestKanbanPageContent:
    """Kanban page renders orders grouped by status."""

    def test_kanban_page_loads_with_200(self, logged_in_client, db_session):
        """Kanban page returns 200 even with no orders."""
        resp = logged_in_client.get(KANBAN_URL)
        assert resp.status_code == 200
        assert b"Kanban" in resp.data

    def test_kanban_shows_orders_grouped_by_status(self, logged_in_client, db_session):
        """Orders appear in their respective status columns."""
        customer = CustomerFactory()
        db_session.commit()

        order_intake = ServiceOrderFactory(
            customer=customer, status="intake", description="Intake order"
        )
        order_progress = ServiceOrderFactory(
            customer=customer, status="in_progress", description="In progress order"
        )
        db_session.commit()

        resp = logged_in_client.get(KANBAN_URL)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert order_intake.order_number in html
        assert order_progress.order_number in html

    def test_kanban_excludes_soft_deleted_orders(self, logged_in_client, db_session):
        """Soft-deleted orders do not appear on the kanban board."""
        customer = CustomerFactory()
        db_session.commit()

        deleted_order = ServiceOrderFactory(customer=customer, status="intake")
        deleted_order.soft_delete()
        db_session.commit()

        resp = logged_in_client.get(KANBAN_URL)
        assert resp.status_code == 200
        assert deleted_order.order_number.encode() not in resp.data

    def test_kanban_shows_picked_up_in_archived_section(self, logged_in_client, db_session):
        """Picked up orders appear in archived toggle, not active columns."""
        customer = CustomerFactory()
        db_session.commit()

        picked_up = ServiceOrderFactory(customer=customer, status="picked_up")
        db_session.commit()

        resp = logged_in_client.get(KANBAN_URL)
        html = resp.data.decode()
        assert picked_up.order_number in html
        assert "Picked Up" in html

    def test_kanban_shows_cancelled_in_archived_section(self, logged_in_client, db_session):
        """Cancelled orders appear in archived toggle."""
        customer = CustomerFactory()
        db_session.commit()

        cancelled = ServiceOrderFactory(customer=customer, status="cancelled")
        db_session.commit()

        resp = logged_in_client.get(KANBAN_URL)
        html = resp.data.decode()
        assert cancelled.order_number in html

    def test_kanban_displays_customer_name(self, logged_in_client, db_session):
        """Cards show the customer display name."""
        customer = CustomerFactory(first_name="Alice", last_name="Diver")
        db_session.commit()

        ServiceOrderFactory(customer=customer, status="intake")
        db_session.commit()

        resp = logged_in_client.get(KANBAN_URL)
        assert b"Alice Diver" in resp.data

    def test_kanban_displays_priority_badge(self, logged_in_client, db_session):
        """Cards show priority badges."""
        customer = CustomerFactory()
        db_session.commit()

        ServiceOrderFactory(customer=customer, status="intake", priority="rush")
        db_session.commit()

        resp = logged_in_client.get(KANBAN_URL)
        assert b"Rush" in resp.data

    def test_kanban_shows_total_count(self, logged_in_client, db_session):
        """The page header shows the total active order count."""
        customer = CustomerFactory()
        db_session.commit()

        ServiceOrderFactory(customer=customer, status="intake")
        ServiceOrderFactory(customer=customer, status="assessment")
        db_session.commit()

        resp = logged_in_client.get(KANBAN_URL)
        assert b"2 active orders" in resp.data


class TestKanbanStatusChange:
    """Tests for POST /orders/<id>/kanban-status."""

    def test_valid_status_transition(self, logged_in_client, db_session):
        """A valid transition returns 200 with success JSON."""
        customer = CustomerFactory()
        db_session.commit()

        order = ServiceOrderFactory(customer=customer, status="intake")
        db_session.commit()

        resp = logged_in_client.post(
            _kanban_status_url(order.id),
            data={"new_status": "assessment"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["new_status"] == "assessment"

    def test_invalid_status_transition(self, logged_in_client, db_session):
        """An invalid transition returns 400 with error message."""
        customer = CustomerFactory()
        db_session.commit()

        order = ServiceOrderFactory(customer=customer, status="intake")
        db_session.commit()

        resp = logged_in_client.post(
            _kanban_status_url(order.id),
            data={"new_status": "completed"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "Cannot transition" in data["error"]

    def test_missing_status_returns_400(self, logged_in_client, db_session):
        """Missing new_status parameter returns 400."""
        customer = CustomerFactory()
        db_session.commit()

        order = ServiceOrderFactory(customer=customer, status="intake")
        db_session.commit()

        resp = logged_in_client.post(
            _kanban_status_url(order.id),
            data={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_kanban_status_requires_auth(self, client, db_session):
        """Unauthenticated users cannot change status."""
        resp = client.post(
            _kanban_status_url(1),
            data={"new_status": "assessment"},
        )
        assert resp.status_code == 302
        assert "/login" in resp.location

    def test_kanban_status_requires_admin_or_tech(self, viewer_client, db_session):
        """Viewer role gets 403 on status change."""
        customer = CustomerFactory()
        db_session.commit()

        order = ServiceOrderFactory(customer=customer, status="intake")
        db_session.commit()

        resp = viewer_client.post(
            _kanban_status_url(order.id),
            data={"new_status": "assessment"},
        )
        assert resp.status_code == 403

    def test_kanban_status_nonexistent_order(self, logged_in_client, db_session):
        """Status change on non-existent order returns 404."""
        resp = logged_in_client.post(
            _kanban_status_url(99999),
            data={"new_status": "assessment"},
        )
        assert resp.status_code == 404


class TestListPageKanbanToggle:
    """The list page should include a link to the kanban view."""

    def test_list_page_has_kanban_link(self, logged_in_client, db_session):
        """The orders list page includes a kanban view toggle."""
        resp = logged_in_client.get("/orders/")
        assert resp.status_code == 200
        assert b"/orders/kanban" in resp.data
