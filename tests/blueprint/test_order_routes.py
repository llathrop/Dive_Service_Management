"""Blueprint tests for service order routes.

Tests listing, creating, viewing, editing, and soft-deleting service
orders via the orders blueprint.  Verifies role-based access control
for anonymous, viewer, technician, and admin users, as well as status
transitions and order item management.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.applied_service import AppliedService
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.labor import LaborEntry
from app.models.parts_used import PartUsed
from app.models.service_item import ServiceItem
from app.models.service_note import ServiceNote
from app.models.service_order import ServiceOrder
from app.models.service_order_item import ServiceOrderItem

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


def _create_service_item(db_session, **overrides):
    """Create and persist a ServiceItem with sensible defaults."""
    defaults = dict(
        name="Test Regulator",
        item_category="Regulator",
        serviceability="serviceable",
    )
    defaults.update(overrides)
    item = ServiceItem(**defaults)
    db.session.add(item)
    db.session.commit()
    return item


def _create_order(db_session, customer=None, **overrides):
    """Create and persist a ServiceOrder with sensible defaults."""
    if customer is None:
        customer = _create_customer(db_session)
    defaults = dict(
        order_number="SO-2026-00001",
        customer_id=customer.id,
        status="intake",
        priority="normal",
        date_received=date.today(),
    )
    defaults.update(overrides)
    order = ServiceOrder(**defaults)
    db.session.add(order)
    db.session.commit()
    return order


def _create_order_with_item(db_session):
    """Create an order with a customer and one order item."""
    customer = _create_customer(db_session)
    si = _create_service_item(db_session)
    order = _create_order(db_session, customer=customer)
    oi = ServiceOrderItem(
        order_id=order.id,
        service_item_id=si.id,
        work_description="Test service",
    )
    db.session.add(oi)
    db.session.commit()
    return order, oi, customer, si


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------

class TestUnauthenticated:
    """Anonymous users are redirected to the login page."""

    def test_list_redirects(self, client):
        response = client.get("/orders/")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_detail_redirects(self, client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
        response = client.get(f"/orders/{oid}")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_get_redirects(self, client):
        response = client.get("/orders/new")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_post_redirects(self, client):
        response = client.post("/orders/new", data={"customer_id": "1"})
        assert response.status_code == 302
        assert "/login" in response.location

    def test_delete_redirects(self, client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
        response = client.post(f"/orders/{oid}/delete")
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Viewer role (read-only -- 403 on write operations)
# ---------------------------------------------------------------------------

class TestViewerAccess:
    """Viewer users can list/view orders but get 403 on create/edit/delete."""

    def test_viewer_can_list_orders(self, viewer_client, app, db_session):
        response = viewer_client.get("/orders/")
        assert response.status_code == 200

    def test_viewer_can_view_order_detail(self, viewer_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
        response = viewer_client.get(f"/orders/{oid}")
        assert response.status_code == 200

    def test_viewer_cannot_create_order(self, viewer_client):
        response = viewer_client.get("/orders/new")
        assert response.status_code == 403

    def test_viewer_cannot_create_order_post(self, viewer_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = viewer_client.post(
            "/orders/new",
            data={
                "customer_id": str(cid),
                "date_received": "2026-03-01",
                "priority": "normal",
            },
        )
        assert response.status_code == 403

    def test_viewer_cannot_delete_order(self, viewer_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
        response = viewer_client.post(f"/orders/{oid}/delete")
        assert response.status_code == 403

    def test_viewer_cannot_edit_order(self, viewer_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
        response = viewer_client.get(f"/orders/{oid}/edit")
        assert response.status_code == 403

    def test_viewer_cannot_change_status(self, viewer_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
        response = viewer_client.post(
            f"/orders/{oid}/status",
            data={"new_status": "assessment"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Technician role (can create/edit but not delete)
# ---------------------------------------------------------------------------

class TestTechnicianAccess:
    """Technician users can create and edit orders but cannot delete."""

    def test_tech_can_list_orders(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/orders/")
        assert response.status_code == 200

    def test_tech_can_view_order_detail(self, logged_in_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
        response = logged_in_client.get(f"/orders/{oid}")
        assert response.status_code == 200

    def test_tech_can_create_order(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = logged_in_client.post(
            "/orders/new",
            data={
                "customer_id": str(cid),
                "status": "intake",
                "priority": "normal",
                "date_received": date.today().isoformat(),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/orders/" in response.location

    def test_tech_can_edit_order(self, logged_in_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
            cid = order.customer_id
        response = logged_in_client.post(
            f"/orders/{oid}/edit",
            data={
                "customer_id": str(cid),
                "status": "intake",
                "priority": "high",
                "date_received": date.today().isoformat(),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert f"/orders/{oid}" in response.location

    def test_tech_cannot_delete_order(self, logged_in_client, app, db_session):
        """Technicians cannot delete orders (admin-only)."""
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
        response = logged_in_client.post(f"/orders/{oid}/delete")
        assert response.status_code == 403

    def test_tech_can_change_status(self, logged_in_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session, status="intake")
            oid = order.id
        response = logged_in_client.post(
            f"/orders/{oid}/status",
            data={"new_status": "assessment"},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_tech_can_add_item(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            si = _create_service_item(db_session)
            order = _create_order(db_session, customer=customer)
            oid = order.id
            si_id = si.id
        response = logged_in_client.post(
            f"/orders/{oid}/items/add",
            data={
                "service_item_id": str(si_id),
                "work_description": "Annual service",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_tech_can_add_note(self, logged_in_client, app, db_session):
        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            oi_id = oi.id
            oid = order.id
        response = logged_in_client.post(
            f"/orders/items/{oi_id}/notes/add",
            data={
                "note_text": "Found worn O-ring.",
                "note_type": "diagnostic",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# Admin role (full CRUD)
# ---------------------------------------------------------------------------

class TestAdminCRUD:
    """Admin users have full access to order routes."""

    def test_admin_can_create_order(self, admin_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = admin_client.post(
            "/orders/new",
            data={
                "customer_id": str(cid),
                "status": "intake",
                "priority": "normal",
                "date_received": date.today().isoformat(),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            order = ServiceOrder.query.filter_by(customer_id=cid).first()
            assert order is not None

    def test_admin_can_edit_order(self, admin_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
            cid = order.customer_id
        response = admin_client.post(
            f"/orders/{oid}/edit",
            data={
                "customer_id": str(cid),
                "status": "intake",
                "priority": "rush",
                "date_received": date.today().isoformat(),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            updated = db.session.get(ServiceOrder, oid)
            assert updated.priority == "rush"

    def test_admin_can_delete_order(self, admin_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session)
            oid = order.id
        response = admin_client.post(
            f"/orders/{oid}/delete", follow_redirects=False
        )
        assert response.status_code == 302

        with app.app_context():
            order = db.session.get(ServiceOrder, oid)
            assert order.is_deleted is True

    def test_admin_can_change_status(self, admin_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session, status="intake")
            oid = order.id
        response = admin_client.post(
            f"/orders/{oid}/status",
            data={"new_status": "assessment"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            updated = db.session.get(ServiceOrder, oid)
            assert updated.status == "assessment"


# ---------------------------------------------------------------------------
# Order creation validation
# ---------------------------------------------------------------------------

class TestOrderCreation:
    """Form validation tests for order creation."""

    def test_create_order_requires_customer(self, logged_in_client, app, db_session):
        """Order creation without a customer should fail validation."""
        response = logged_in_client.post(
            "/orders/new",
            data={
                "customer_id": "",
                "date_received": date.today().isoformat(),
                "priority": "normal",
            },
            follow_redirects=False,
        )
        # Should re-render form (200) because validation failed, not redirect
        assert response.status_code == 200

    def test_create_order_requires_date_received(self, logged_in_client, app, db_session):
        """Order creation without date_received should fail validation."""
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = logged_in_client.post(
            "/orders/new",
            data={
                "customer_id": str(cid),
                "date_received": "",
                "priority": "normal",
            },
            follow_redirects=False,
        )
        # Should re-render form (200) because validation failed
        assert response.status_code == 200

    def test_create_order_redirects_to_detail(self, logged_in_client, app, db_session):
        """Successful order creation redirects to the order detail page."""
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = logged_in_client.post(
            "/orders/new",
            data={
                "customer_id": str(cid),
                "status": "intake",
                "priority": "normal",
                "date_received": date.today().isoformat(),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/orders/" in response.location


# ---------------------------------------------------------------------------
# Status workflow
# ---------------------------------------------------------------------------

class TestOrderStatusWorkflow:
    """Tests for status transition routes."""

    def test_status_intake_to_assessment(self, logged_in_client, app, db_session):
        with app.app_context():
            order = _create_order(db_session, status="intake")
            oid = order.id
        response = logged_in_client.post(
            f"/orders/{oid}/status",
            data={"new_status": "assessment"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            updated = db.session.get(ServiceOrder, oid)
            assert updated.status == "assessment"

    def test_status_invalid_transition_flashes_error(self, logged_in_client, app, db_session):
        """An invalid status transition should redirect and flash an error."""
        with app.app_context():
            order = _create_order(db_session, status="intake")
            oid = order.id
        response = logged_in_client.post(
            f"/orders/{oid}/status",
            data={"new_status": "completed"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # The order status should remain intake
        with app.app_context():
            order = db.session.get(ServiceOrder, oid)
            assert order.status == "intake"

    def test_status_completed_sets_date(self, logged_in_client, app, db_session):
        """Transitioning to 'completed' sets date_completed."""
        with app.app_context():
            order = _create_order(db_session, status="in_progress")
            oid = order.id
        response = logged_in_client.post(
            f"/orders/{oid}/status",
            data={"new_status": "completed"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            updated = db.session.get(ServiceOrder, oid)
            assert updated.status == "completed"
            assert updated.date_completed is not None


# ---------------------------------------------------------------------------
# Order items
# ---------------------------------------------------------------------------

class TestOrderItems:
    """Tests for adding and removing order items via routes."""

    def test_add_item_to_order(self, logged_in_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            si = _create_service_item(db_session)
            order = _create_order(db_session, customer=customer)
            oid = order.id
            si_id = si.id
        response = logged_in_client.post(
            f"/orders/{oid}/items/add",
            data={
                "service_item_id": str(si_id),
                "work_description": "Full annual service",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            items = ServiceOrderItem.query.filter_by(order_id=oid).all()
            assert len(items) == 1
            assert items[0].work_description == "Full annual service"

    def test_remove_item_from_order(self, logged_in_client, app, db_session):
        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            oid = order.id
            oi_id = oi.id
        response = logged_in_client.post(
            f"/orders/items/{oi_id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            items = ServiceOrderItem.query.filter_by(order_id=oid).all()
            assert len(items) == 0


# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------

class TestOrderSearch:
    """Verify search and filter query parameters on the list page."""

    def test_search_by_order_number(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_order(db_session, order_number="SO-2026-99999")
        response = logged_in_client.get("/orders/?q=99999")
        assert response.status_code == 200
        assert b"SO-2026-99999" in response.data

    def test_filter_by_status(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_order(db_session, status="in_progress", order_number="SO-2026-88888")
        response = logged_in_client.get("/orders/?status=in_progress")
        assert response.status_code == 200
        assert b"SO-2026-88888" in response.data

    def test_filter_by_priority(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_order(db_session, priority="rush", order_number="SO-2026-77777")
        response = logged_in_client.get("/orders/?priority=rush")
        assert response.status_code == 200
        assert b"SO-2026-77777" in response.data


# ---------------------------------------------------------------------------
# Helpers for sub-entity tests
# ---------------------------------------------------------------------------

def _create_inventory_item(db_session, **overrides):
    defaults = dict(
        name="Test Seal",
        category="Seals",
        quantity_in_stock=10,
        purchase_cost=Decimal("5.00"),
        resale_price=Decimal("15.00"),
        is_active=True,
    )
    defaults.update(overrides)
    item = InventoryItem(**defaults)
    db.session.add(item)
    db.session.commit()
    return item


# ---------------------------------------------------------------------------
# Applied services (add/remove)
# ---------------------------------------------------------------------------

class TestAppliedServices:
    """Tests for adding and removing applied services via routes."""

    def test_add_service_to_order_item(self, logged_in_client, app, db_session):
        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            oid = order.id
            oi_id = oi.id
        response = logged_in_client.post(
            f"/orders/items/{oi_id}/services/add",
            data={
                "service_name": "Leak Test",
                "quantity": "1.00",
                "unit_price": "50.00",
                "discount_percent": "0.00",
                "is_taxable": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        with app.app_context():
            services = AppliedService.query.filter_by(
                service_order_item_id=oi_id
            ).all()
            assert len(services) == 1
            assert services[0].service_name == "Leak Test"

    def test_remove_service(self, logged_in_client, app, db_session):
        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            svc = AppliedService(
                service_order_item_id=oi.id,
                service_name="Test Service",
                quantity=Decimal("1.00"),
                unit_price=Decimal("100.00"),
                line_total=Decimal("100.00"),
            )
            db.session.add(svc)
            db.session.commit()
            svc_id = svc.id
        response = logged_in_client.post(
            f"/orders/services/{svc_id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 302
        with app.app_context():
            assert db.session.get(AppliedService, svc_id) is None


# ---------------------------------------------------------------------------
# Parts used (add/remove)
# ---------------------------------------------------------------------------

class TestPartsUsed:
    """Tests for adding and removing parts via routes."""

    def test_add_part_to_order_item(self, logged_in_client, app, db_session):
        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            inv = _create_inventory_item(db_session)
            oi_id = oi.id
            inv_id = inv.id
        response = logged_in_client.post(
            f"/orders/items/{oi_id}/parts/add",
            data={
                "inventory_item_id": str(inv_id),
                "quantity": "2.00",
                "unit_price_at_use": "15.00",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        with app.app_context():
            parts = PartUsed.query.filter_by(
                service_order_item_id=oi_id
            ).all()
            assert len(parts) == 1
            # Inventory should be deducted
            inv_item = db.session.get(InventoryItem, inv_id)
            assert inv_item.quantity_in_stock == 8  # 10 - 2

    def test_add_part_catches_value_error(self, logged_in_client, app, db_session):
        """When add_part_used raises ValueError, the error is flashed, not a 500."""
        from unittest.mock import patch

        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            oi_id = oi.id
            inv = _create_inventory_item(db_session)
            inv_id = inv.id

        with patch(
            "app.blueprints.orders.order_service.add_part_used",
            side_effect=ValueError("Inventory item 99999 not found."),
        ):
            response = logged_in_client.post(
                f"/orders/items/{oi_id}/parts/add",
                data={
                    "inventory_item_id": str(inv_id),
                    "quantity": "1.00",
                    "unit_price_at_use": "5.00",
                },
                follow_redirects=True,
            )
        # Should redirect with flash, not 500
        assert response.status_code == 200
        assert b"not found" in response.data

    def test_remove_part_restores_inventory(self, logged_in_client, app, db_session):
        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            inv = _create_inventory_item(db_session)
            part = PartUsed(
                service_order_item_id=oi.id,
                inventory_item_id=inv.id,
                quantity=Decimal("3.00"),
                unit_cost_at_use=Decimal("5.00"),
                unit_price_at_use=Decimal("15.00"),
            )
            db.session.add(part)
            inv.quantity_in_stock -= 3  # simulate deduction
            db.session.commit()
            part_id = part.id
            inv_id = inv.id
        response = logged_in_client.post(
            f"/orders/parts/{part_id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 302
        with app.app_context():
            assert db.session.get(PartUsed, part_id) is None
            inv_item = db.session.get(InventoryItem, inv_id)
            assert inv_item.quantity_in_stock == 10  # restored


# ---------------------------------------------------------------------------
# Labor entries (add/remove)
# ---------------------------------------------------------------------------

class TestLaborEntries:
    """Tests for adding and removing labor entries via routes."""

    def test_add_labor_to_order_item(self, logged_in_client, app, db_session):
        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            oi_id = oi.id
            # Create a tech user for the labor entry
            user_datastore = app.extensions["security"].datastore
            tech_role = user_datastore.find_or_create_role(name="technician")
            tech = user_datastore.create_user(
                username="labor_tech",
                email="labor_tech@example.com",
                password="password",
                first_name="Labor",
                last_name="Tech",
            )
            user_datastore.add_role_to_user(tech, tech_role)
            db.session.commit()
            tech_id = tech.id
        response = logged_in_client.post(
            f"/orders/items/{oi_id}/labor/add",
            data={
                "tech_id": str(tech_id),
                "hours": "2.50",
                "hourly_rate": "75.00",
                "description": "Seal replacement",
                "work_date": date.today().isoformat(),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        with app.app_context():
            entries = LaborEntry.query.filter_by(
                service_order_item_id=oi_id
            ).all()
            assert len(entries) == 1
            assert entries[0].description == "Seal replacement"

    def test_remove_labor_entry(self, logged_in_client, app, db_session):
        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            user_datastore = app.extensions["security"].datastore
            tech_role = user_datastore.find_or_create_role(name="technician")
            tech = user_datastore.create_user(
                username="labor_tech2",
                email="labor_tech2@example.com",
                password="password",
                first_name="Labor",
                last_name="Tech2",
            )
            user_datastore.add_role_to_user(tech, tech_role)
            db.session.flush()
            labor = LaborEntry(
                service_order_item_id=oi.id,
                tech_id=tech.id,
                hours=Decimal("1.00"),
                hourly_rate=Decimal("75.00"),
                work_date=date.today(),
            )
            db.session.add(labor)
            db.session.commit()
            labor_id = labor.id
        response = logged_in_client.post(
            f"/orders/labor/{labor_id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 302
        with app.app_context():
            assert db.session.get(LaborEntry, labor_id) is None


# ---------------------------------------------------------------------------
# Service notes (add)
# ---------------------------------------------------------------------------

class TestServiceNotes:
    """Tests for adding notes via routes."""

    def test_add_note_to_order_item(self, logged_in_client, app, db_session):
        with app.app_context():
            order, oi, _, _ = _create_order_with_item(db_session)
            oi_id = oi.id
        response = logged_in_client.post(
            f"/orders/items/{oi_id}/notes/add",
            data={
                "note_text": "Found small leak at shoulder seam",
                "note_type": "diagnostic",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        with app.app_context():
            notes = ServiceNote.query.filter_by(
                service_order_item_id=oi_id
            ).all()
            assert len(notes) == 1
            assert notes[0].note_type == "diagnostic"
