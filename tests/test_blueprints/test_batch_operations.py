"""Tests for batch operations on orders, customers, and inventory list views."""

import pytest

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.service_order import ServiceOrder
from tests.factories import (
    BaseFactory,
    CustomerFactory,
    InventoryItemFactory,
    ServiceOrderFactory,
)

pytestmark = pytest.mark.blueprint


@pytest.fixture(autouse=True)
def _set_session(db_session):
    """Inject the test DB session into all factories."""
    BaseFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    InventoryItemFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session


# =========================================================================
# Orders batch operations
# =========================================================================


class TestBatchOrderChangeStatus:
    """POST /orders/batch with change_status action."""

    def test_batch_change_order_status(self, logged_in_client, app):
        """Select 2 orders in intake, change to assessment, verify both changed."""
        with app.app_context():
            o1 = ServiceOrderFactory(status="intake")
            o2 = ServiceOrderFactory(status="intake")

            resp = logged_in_client.post("/orders/batch", data={
                "selected_ids": [o1.id, o2.id],
                "action": "change_status",
                "target_status": "assessment",
            }, follow_redirects=True)

            assert resp.status_code == 200
            assert b"2 order(s) updated" in resp.data

            updated1 = db.session.get(ServiceOrder, o1.id)
            updated2 = db.session.get(ServiceOrder, o2.id)
            assert updated1.status == "assessment"
            assert updated2.status == "assessment"

    def test_batch_change_status_invalid_transition(self, logged_in_client, app):
        """Attempting an invalid status transition counts as errors."""
        with app.app_context():
            # picked_up is a terminal state, cannot go to intake
            o1 = ServiceOrderFactory(status="picked_up")

            resp = logged_in_client.post("/orders/batch", data={
                "selected_ids": [o1.id],
                "action": "change_status",
                "target_status": "intake",
            }, follow_redirects=True)

            assert resp.status_code == 200
            assert b"could not be updated" in resp.data


class TestBatchOrderCancel:
    """POST /orders/batch with cancel action."""

    def test_batch_cancel_orders(self, logged_in_client, app):
        """Cancel 3 orders and verify all cancelled with audit log entries."""
        with app.app_context():
            orders = [ServiceOrderFactory(status="intake") for _ in range(3)]
            ids = [o.id for o in orders]

            resp = logged_in_client.post("/orders/batch", data={
                "selected_ids": ids,
                "action": "cancel",
            }, follow_redirects=True)

            assert resp.status_code == 200
            assert b"3 order(s) updated" in resp.data

            for oid in ids:
                order = db.session.get(ServiceOrder, oid)
                assert order.status == "cancelled"

            # Verify audit log entries exist
            audit_entries = AuditLog.query.filter_by(
                entity_type="service_order",
                action="status_change",
            ).all()
            assert len(audit_entries) >= 3


class TestBatchOrderAssignTech:
    """POST /orders/batch with assign_tech action."""

    def test_batch_assign_tech(self, admin_client, app, db_session):
        """Assign a technician to 2 orders via batch."""
        from flask_security import hash_password

        with app.app_context():
            user_datastore = app.extensions["security"].datastore
            tech_role = user_datastore.find_or_create_role(name="technician")
            tech = user_datastore.create_user(
                username="batchtech",
                email="batchtech@example.com",
                password=hash_password("password"),
                first_name="Batch",
                last_name="Tech",
            )
            user_datastore.add_role_to_user(tech, tech_role)
            db_session.commit()

            o1 = ServiceOrderFactory()
            o2 = ServiceOrderFactory()

            resp = admin_client.post("/orders/batch", data={
                "selected_ids": [o1.id, o2.id],
                "action": "assign_tech",
                "tech_id": tech.id,
            }, follow_redirects=True)

            assert resp.status_code == 200
            assert b"2 order(s) updated" in resp.data

            updated1 = db.session.get(ServiceOrder, o1.id)
            updated2 = db.session.get(ServiceOrder, o2.id)
            assert updated1.assigned_tech_id == tech.id
            assert updated2.assigned_tech_id == tech.id

            audit_entries = AuditLog.query.filter_by(
                entity_type="service_order",
                action="update",
                field_name="assigned_tech_id",
            ).all()
            assert len(audit_entries) == 2
            assert {entry.new_value for entry in audit_entries} == {str(tech.id)}

    def test_batch_assign_tech_rejects_inactive_tech(self, admin_client, app, db_session):
        """Inactive technicians are not valid batch assignment targets."""
        from flask_security import hash_password

        with app.app_context():
            user_datastore = app.extensions["security"].datastore
            tech_role = user_datastore.find_or_create_role(name="technician")
            tech = user_datastore.create_user(
                username="inactivebatchtech",
                email="inactivebatchtech@example.com",
                password=hash_password("password"),
                first_name="Inactive",
                last_name="Tech",
                active=False,
            )
            user_datastore.add_role_to_user(tech, tech_role)
            db_session.commit()

            order = ServiceOrderFactory()

            resp = admin_client.post("/orders/batch", data={
                "selected_ids": [order.id],
                "action": "assign_tech",
                "tech_id": tech.id,
            }, follow_redirects=True)

            assert resp.status_code == 200
            assert b"Invalid technician specified" in resp.data

            updated = db.session.get(ServiceOrder, order.id)
            assert updated.assigned_tech_id is None

    def test_batch_assign_tech_rolls_back_on_failure(self, admin_client, app, db_session):
        """If one selected order fails, no assignment should be committed."""
        from flask_security import hash_password

        with app.app_context():
            user_datastore = app.extensions["security"].datastore
            tech_role = user_datastore.find_or_create_role(name="technician")
            tech = user_datastore.create_user(
                username="rollbacktech",
                email="rollbacktech@example.com",
                password=hash_password("password"),
                first_name="Roll",
                last_name="Back",
            )
            user_datastore.add_role_to_user(tech, tech_role)
            db_session.commit()

            o1 = ServiceOrderFactory()
            o2 = ServiceOrderFactory()
            o2.soft_delete()
            db.session.commit()

            resp = admin_client.post("/orders/batch", data={
                "selected_ids": [o1.id, o2.id],
                "action": "assign_tech",
                "tech_id": tech.id,
            }, follow_redirects=True)

            assert resp.status_code == 200
            assert b"could not be updated" in resp.data

            updated1 = db.session.get(ServiceOrder, o1.id)
            updated2 = db.session.get(ServiceOrder, o2.id)
            assert updated1.assigned_tech_id is None
            assert updated2.is_deleted is True


class TestBatchOrderListUi:
    """The orders list batch controls should be wired for browser use."""

    def test_change_status_controls_are_wired(self, logged_in_client, app):
        with app.app_context():
            ServiceOrderFactory()

            resp = logged_in_client.get("/orders/")

            assert resp.status_code == 200
            assert b'x-ref="targetStatus"' in resp.data
            assert b'x-model="targetStatus"' in resp.data


# =========================================================================
# Customers batch operations
# =========================================================================


class TestBatchCustomerDeactivate:
    """POST /customers/batch with deactivate action."""

    def test_batch_deactivate_customers(self, admin_client, app):
        """Deactivate 2 customers and verify they are soft-deleted."""
        with app.app_context():
            c1 = CustomerFactory()
            c2 = CustomerFactory()

            resp = admin_client.post("/customers/batch", data={
                "selected_ids": [c1.id, c2.id],
                "action": "deactivate",
            }, follow_redirects=True)

            assert resp.status_code == 200
            assert b"2 customer(s) updated" in resp.data

            updated1 = db.session.get(Customer, c1.id)
            updated2 = db.session.get(Customer, c2.id)
            assert updated1.is_deleted is True
            assert updated2.is_deleted is True

            audit_entries = AuditLog.query.filter_by(
                entity_type="customer",
                action="delete",
                field_name="is_deleted",
            ).all()
            assert len(audit_entries) == 2
            assert {entry.old_value for entry in audit_entries} == {"False"}
            assert {entry.new_value for entry in audit_entries} == {"True"}

    def test_batch_deactivate_customers_forbidden_for_technician(self, logged_in_client, app):
        """Technicians should not gain batch deactivate access."""
        with app.app_context():
            customer = CustomerFactory()

            resp = logged_in_client.post("/customers/batch", data={
                "selected_ids": [customer.id],
                "action": "deactivate",
            }, follow_redirects=False)

            assert resp.status_code == 403

    def test_customer_list_hides_batch_controls_for_technician(self, logged_in_client, app):
        """Technicians should not see destructive batch controls on customer lists."""
        with app.app_context():
            CustomerFactory()

            resp = logged_in_client.get("/customers/")

            assert resp.status_code == 200
            assert b'id="batch-form"' not in resp.data
            assert b'id="batch-select-all"' not in resp.data


class TestBatchCustomerListUi:
    """Non-admin users should still see customer rows but no batch controls."""

    def test_customer_list_renders_rows_for_technician(self, logged_in_client, app):
        with app.app_context():
            customer = CustomerFactory(first_name="Visible", last_name="Customer")

            resp = logged_in_client.get("/customers/")

            assert resp.status_code == 200
            assert b"Visible Customer" in resp.data
            assert b'id="batch-form"' not in resp.data
            assert b'id="batch-select-all"' not in resp.data

    def test_customer_list_renders_rows_for_viewer(self, viewer_client, app):
        with app.app_context():
            customer = CustomerFactory(first_name="Viewer", last_name="Row")

            resp = viewer_client.get("/customers/")

            assert resp.status_code == 200
            assert b"Viewer Row" in resp.data
            assert b'id="batch-form"' not in resp.data
            assert b'id="batch-select-all"' not in resp.data


# =========================================================================
# Inventory batch operations
# =========================================================================


class TestBatchInventoryDeactivate:
    """POST /inventory/batch with deactivate action."""

    def test_batch_deactivate_inventory(self, admin_client, app):
        """Deactivate 3 inventory items and verify is_active=False."""
        with app.app_context():
            items = [InventoryItemFactory(is_active=True) for _ in range(3)]
            ids = [i.id for i in items]

            resp = admin_client.post("/inventory/batch", data={
                "selected_ids": ids,
                "action": "deactivate",
            }, follow_redirects=True)

            assert resp.status_code == 200
            assert b"3 item(s) updated" in resp.data

            for iid in ids:
                item = db.session.get(InventoryItem, iid)
                assert item.is_active is False

            audit_entries = AuditLog.query.filter_by(
                entity_type="inventory_item",
                action="update",
                field_name="is_active",
            ).all()
            assert len(audit_entries) == 3
            assert {entry.old_value for entry in audit_entries} == {"True"}
            assert {entry.new_value for entry in audit_entries} == {"False"}

    def test_batch_deactivate_inventory_forbidden_for_technician(self, logged_in_client, app):
        """Technicians should not gain batch deactivate access."""
        with app.app_context():
            item = InventoryItemFactory(is_active=True)

            resp = logged_in_client.post("/inventory/batch", data={
                "selected_ids": [item.id],
                "action": "deactivate",
            }, follow_redirects=False)

            assert resp.status_code == 403

    def test_inventory_list_hides_batch_controls_for_technician(self, logged_in_client, app):
        """Technicians should not see destructive batch controls on inventory lists."""
        with app.app_context():
            InventoryItemFactory(name="Visible Part", is_active=True)

            resp = logged_in_client.get("/inventory/")

            assert resp.status_code == 200
            assert b"Visible Part" in resp.data
            assert b'id="batch-form"' not in resp.data
            assert b'id="batch-select-all"' not in resp.data

    def test_inventory_list_renders_rows_for_viewer(self, viewer_client, app):
        """Viewers should still see inventory rows even without batch controls."""
        with app.app_context():
            InventoryItemFactory(name="Viewer Part", is_active=True)

            resp = viewer_client.get("/inventory/")

            assert resp.status_code == 200
            assert b"Viewer Part" in resp.data
            assert b'id="batch-form"' not in resp.data
            assert b'id="batch-select-all"' not in resp.data


class TestBatchInventoryActivate:
    """POST /inventory/batch with activate action."""

    def test_batch_activate_inventory(self, admin_client, app):
        """Activate inactive inventory items."""
        with app.app_context():
            items = [InventoryItemFactory(is_active=False) for _ in range(2)]
            ids = [i.id for i in items]

            resp = admin_client.post("/inventory/batch", data={
                "selected_ids": ids,
                "action": "activate",
            }, follow_redirects=True)

            assert resp.status_code == 200
            assert b"2 item(s) updated" in resp.data

            for iid in ids:
                item = db.session.get(InventoryItem, iid)
                assert item.is_active is True

            audit_entries = AuditLog.query.filter_by(
                entity_type="inventory_item",
                action="update",
                field_name="is_active",
            ).all()
            assert len(audit_entries) == 2
            assert {entry.old_value for entry in audit_entries} == {"False"}
            assert {entry.new_value for entry in audit_entries} == {"True"}


# =========================================================================
# Error and auth cases
# =========================================================================


class TestBatchInvalidAction:
    """Batch endpoint rejects invalid action values."""

    def test_batch_invalid_action_orders(self, logged_in_client, app):
        with app.app_context():
            o1 = ServiceOrderFactory()
            resp = logged_in_client.post("/orders/batch", data={
                "selected_ids": [o1.id],
                "action": "nuke_everything",
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b"Invalid batch action" in resp.data

    def test_batch_invalid_action_customers(self, admin_client, app):
        with app.app_context():
            c1 = CustomerFactory()
            resp = admin_client.post("/customers/batch", data={
                "selected_ids": [c1.id],
                "action": "destroy",
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b"Invalid batch action" in resp.data

    def test_batch_invalid_action_inventory(self, admin_client, app):
        with app.app_context():
            i1 = InventoryItemFactory()
            resp = admin_client.post("/inventory/batch", data={
                "selected_ids": [i1.id],
                "action": "explode",
            }, follow_redirects=True)
            assert resp.status_code == 200
            assert b"Invalid batch action" in resp.data


class TestBatchViewerDenied:
    """Viewer role cannot access batch endpoints (403)."""

    def test_batch_viewer_denied_orders(self, viewer_client, app):
        resp = viewer_client.post("/orders/batch", data={
            "selected_ids": [1],
            "action": "cancel",
        }, follow_redirects=False)
        assert resp.status_code == 403

    def test_batch_viewer_denied_customers(self, viewer_client, app):
        resp = viewer_client.post("/customers/batch", data={
            "selected_ids": [1],
            "action": "deactivate",
        }, follow_redirects=False)
        assert resp.status_code == 403

    def test_batch_viewer_denied_inventory(self, viewer_client, app):
        resp = viewer_client.post("/inventory/batch", data={
            "selected_ids": [1],
            "action": "deactivate",
        }, follow_redirects=False)
        assert resp.status_code == 403


class TestBatchEmptySelection:
    """Empty selected_ids flashes a warning."""

    def test_batch_empty_selection_orders(self, logged_in_client):
        resp = logged_in_client.post("/orders/batch", data={
            "action": "cancel",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"No orders selected" in resp.data

    def test_batch_empty_selection_customers(self, admin_client):
        resp = admin_client.post("/customers/batch", data={
            "action": "deactivate",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"No customers selected" in resp.data

    def test_batch_empty_selection_inventory(self, admin_client):
        resp = admin_client.post("/inventory/batch", data={
            "action": "deactivate",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"No inventory items selected" in resp.data
