"""Tests verifying that audit logging is wired into CRUD operations.

Each test performs a write operation and then checks that an AuditLog
entry was created with the correct action, entity_type, and entity_id.
"""

from datetime import date
from decimal import Decimal

import pytest
from flask_security import hash_password

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.service_item import ServiceItem
from app.models.service_order import ServiceOrder
from app.services import audit_service, invoice_service, order_service
from tests.factories import (
    CustomerFactory,
    InventoryItemFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
    UserFactory,
)


def _set_session(db_session, *factories):
    for f in factories:
        f._meta.sqlalchemy_session = db_session


# ── Blueprint tests (via test client) ─────────────────────────────────


class TestCustomerAuditWiring:
    """Audit logging for customer blueprint operations."""

    def test_create_customer_logs_audit(self, app, db_session, logged_in_client):
        resp = logged_in_client.post(
            "/customers/new",
            data={
                "customer_type": "individual",
                "first_name": "Test",
                "last_name": "Customer",
                "email": "test@example.com",
                "phone_primary": "555-1234",
                "preferred_contact": "email",
                "csrf_token": _get_csrf(logged_in_client, "/customers/new"),
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        entry = AuditLog.query.filter_by(
            action="create", entity_type="customer"
        ).first()
        assert entry is not None
        assert entry.entity_id is not None

    def test_edit_customer_logs_audit(self, app, db_session, logged_in_client):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory(
            first_name="Old", last_name="Name",
            email="old@example.com",
        )
        db_session.commit()

        csrf = _get_csrf(logged_in_client, f"/customers/{customer.id}/edit")
        logged_in_client.post(
            f"/customers/{customer.id}/edit",
            data={
                "customer_type": "individual",
                "first_name": "New",
                "last_name": "Name",
                "email": "old@example.com",
                "phone_primary": "555-1234",
                "preferred_contact": "email",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        entry = AuditLog.query.filter_by(
            action="update", entity_type="customer"
        ).first()
        assert entry is not None
        assert entry.entity_id == customer.id

    def test_delete_customer_logs_audit(self, app, db_session, admin_client):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory(email="del@example.com")
        db_session.commit()

        csrf = _get_csrf(admin_client, f"/customers/{customer.id}")
        admin_client.post(
            f"/customers/{customer.id}/delete",
            data={"csrf_token": csrf},
            follow_redirects=True,
        )
        entry = AuditLog.query.filter_by(
            action="delete", entity_type="customer"
        ).first()
        assert entry is not None
        assert entry.entity_id == customer.id


class TestInventoryAuditWiring:
    """Audit logging for inventory blueprint operations."""

    def test_create_inventory_logs_audit(self, app, db_session, logged_in_client):
        resp = logged_in_client.post(
            "/inventory/new",
            data={
                "name": "Test Part",
                "category": "Parts",
                "quantity_in_stock": "10.00",
                "reorder_level": "2.00",
                "is_active": "y",
                "unit_of_measure": "each",
                "csrf_token": _get_csrf(logged_in_client, "/inventory/new"),
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        entry = AuditLog.query.filter_by(
            action="create", entity_type="inventory_item"
        ).first()
        assert entry is not None

    def test_delete_inventory_logs_audit(self, app, db_session, admin_client):
        _set_session(db_session, InventoryItemFactory, UserFactory)
        item = InventoryItemFactory()
        db_session.commit()

        csrf = _get_csrf(admin_client, f"/inventory/{item.id}")
        admin_client.post(
            f"/inventory/{item.id}/delete",
            data={"csrf_token": csrf},
            follow_redirects=True,
        )
        entry = AuditLog.query.filter_by(
            action="delete", entity_type="inventory_item"
        ).first()
        assert entry is not None
        assert entry.entity_id == item.id

    def test_stock_adjustment_logs_audit(self, app, db_session, logged_in_client):
        _set_session(db_session, InventoryItemFactory, UserFactory)
        item = InventoryItemFactory(quantity_in_stock=Decimal("10"))
        db_session.commit()

        csrf = _get_csrf(logged_in_client, f"/inventory/{item.id}")
        logged_in_client.post(
            f"/inventory/{item.id}/adjust",
            data={
                "adjustment": "5.00",
                "reason": "Restock",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        entry = AuditLog.query.filter_by(
            action="update",
            entity_type="inventory_item",
            field_name="quantity_in_stock",
        ).first()
        assert entry is not None
        assert entry.old_value == "10.00"
        assert entry.new_value == "15.00"


class TestServiceItemAuditWiring:
    """Audit logging for service item blueprint operations."""

    def test_create_service_item_logs_audit(self, app, db_session, logged_in_client):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        db_session.commit()

        resp = logged_in_client.post(
            "/items/new",
            data={
                "name": "Test Regulator",
                "item_category": "Regulator",
                "serviceability": "serviceable",
                "customer_id": str(customer.id),
                "csrf_token": _get_csrf(logged_in_client, "/items/new"),
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        entry = AuditLog.query.filter_by(
            action="create", entity_type="service_item"
        ).first()
        assert entry is not None

    def test_delete_service_item_logs_audit(self, app, db_session, admin_client):
        _set_session(db_session, ServiceItemFactory, CustomerFactory, UserFactory)
        item = ServiceItemFactory()
        db_session.commit()

        csrf = _get_csrf(admin_client, f"/items/{item.id}")
        admin_client.post(
            f"/items/{item.id}/delete",
            data={"csrf_token": csrf},
            follow_redirects=True,
        )
        entry = AuditLog.query.filter_by(
            action="delete", entity_type="service_item"
        ).first()
        assert entry is not None


# ── Service layer tests ───────────────────────────────────────────────


class TestOrderServiceAuditWiring:
    """Audit logging for order_service operations."""

    def test_create_order_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        order = order_service.create_order(
            {"customer_id": customer.id},
            created_by=user.id,
        )
        entry = AuditLog.query.filter_by(
            action="create", entity_type="service_order"
        ).first()
        assert entry is not None
        assert entry.entity_id == order.id
        assert entry.user_id == user.id

    def test_update_order_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory, ServiceOrderFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        order = order_service.create_order(
            {"customer_id": customer.id}, created_by=user.id,
        )
        # Clear the create audit entry
        AuditLog.query.delete()
        db_session.commit()

        order_service.update_order(
            order.id, {"description": "updated"}, user_id=user.id,
        )
        entry = AuditLog.query.filter_by(
            action="update", entity_type="service_order"
        ).first()
        assert entry is not None
        assert entry.entity_id == order.id

    def test_change_status_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        order = order_service.create_order(
            {"customer_id": customer.id, "status": "intake"},
            created_by=user.id,
        )

        order, success = order_service.change_status(
            order.id, "assessment", user_id=user.id,
        )
        assert success
        entry = AuditLog.query.filter_by(
            action="status_change", entity_type="service_order"
        ).first()
        assert entry is not None
        assert entry.field_name == "status"
        assert entry.old_value == "intake"
        assert entry.new_value == "assessment"

    def test_delete_order_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        order = order_service.create_order(
            {"customer_id": customer.id}, created_by=user.id,
        )
        order_service.delete_order(order.id, user_id=user.id)
        entry = AuditLog.query.filter_by(
            action="delete", entity_type="service_order"
        ).first()
        assert entry is not None

    def test_add_order_item_logs_audit(self, app, db_session):
        _set_session(
            db_session, CustomerFactory, UserFactory,
            ServiceItemFactory,
        )
        customer = CustomerFactory()
        user = UserFactory()
        item = ServiceItemFactory(customer=customer)
        db_session.commit()

        order = order_service.create_order(
            {"customer_id": customer.id}, created_by=user.id,
        )
        order_item = order_service.add_order_item(order.id, item.id)
        entry = AuditLog.query.filter_by(
            action="create", entity_type="service_order_item"
        ).first()
        assert entry is not None
        assert entry.entity_id == order_item.id

    def test_add_labor_entry_logs_audit(self, app, db_session):
        _set_session(
            db_session, CustomerFactory, UserFactory,
            ServiceItemFactory,
        )
        customer = CustomerFactory()
        user = UserFactory()
        item = ServiceItemFactory(customer=customer)
        db_session.commit()

        order = order_service.create_order(
            {"customer_id": customer.id}, created_by=user.id,
        )
        oi = order_service.add_order_item(order.id, item.id)
        entry = order_service.add_labor_entry(
            oi.id, user.id, Decimal("2.0"), Decimal("50.00"),
        )
        log = AuditLog.query.filter_by(
            action="create", entity_type="labor_entry"
        ).first()
        assert log is not None
        assert log.entity_id == entry.id

    def test_add_part_used_logs_audit(self, app, db_session):
        _set_session(
            db_session, CustomerFactory, UserFactory,
            ServiceItemFactory, InventoryItemFactory,
        )
        customer = CustomerFactory()
        user = UserFactory()
        svc_item = ServiceItemFactory(customer=customer)
        inv_item = InventoryItemFactory(
            quantity_in_stock=Decimal("20"),
            resale_price=Decimal("10.00"),
        )
        db_session.commit()

        order = order_service.create_order(
            {"customer_id": customer.id}, created_by=user.id,
        )
        oi = order_service.add_order_item(order.id, svc_item.id)
        part = order_service.add_part_used(
            oi.id, inv_item.id, Decimal("2"), added_by=user.id,
        )
        log = AuditLog.query.filter_by(
            action="create", entity_type="part_used"
        ).first()
        assert log is not None
        assert log.entity_id == part.id


class TestInvoiceServiceAuditWiring:
    """Audit logging for invoice_service operations."""

    def test_create_invoice_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        invoice = invoice_service.create_invoice(
            {"customer_id": customer.id}, created_by=user.id,
        )
        entry = AuditLog.query.filter_by(
            action="create", entity_type="invoice"
        ).first()
        assert entry is not None
        assert entry.entity_id == invoice.id

    def test_invoice_status_change_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        invoice = invoice_service.create_invoice(
            {"customer_id": customer.id, "status": "draft"},
            created_by=user.id,
        )
        inv, success = invoice_service.change_status(
            invoice.id, "sent", user_id=user.id,
        )
        assert success
        entry = AuditLog.query.filter_by(
            action="status_change", entity_type="invoice"
        ).first()
        assert entry is not None
        assert entry.field_name == "status"
        assert entry.old_value == "draft"
        assert entry.new_value == "sent"

    def test_void_invoice_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        invoice = invoice_service.create_invoice(
            {"customer_id": customer.id, "status": "draft"},
            created_by=user.id,
        )
        invoice_service.void_invoice(invoice.id, user_id=user.id)
        entry = AuditLog.query.filter_by(
            action="status_change",
            entity_type="invoice",
            new_value="void",
        ).first()
        assert entry is not None

    def test_record_payment_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        invoice = invoice_service.create_invoice(
            {
                "customer_id": customer.id,
                "status": "sent",
                "tax_rate": Decimal("0"),
            },
            created_by=user.id,
        )
        # Add a line item so there's a total
        invoice_service.add_line_item(invoice.id, {
            "line_type": "service",
            "description": "Test",
            "quantity": 1,
            "unit_price": Decimal("100.00"),
        })

        payment = invoice_service.record_payment(
            invoice.id,
            {
                "payment_type": "payment",
                "amount": Decimal("50.00"),
                "payment_date": date.today(),
                "payment_method": "cash",
            },
            recorded_by=user.id,
        )
        entry = AuditLog.query.filter_by(
            action="create", entity_type="payment"
        ).first()
        assert entry is not None
        assert entry.entity_id == payment.id
        assert entry.new_value == "50.00"

    def test_update_invoice_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        invoice = invoice_service.create_invoice(
            {"customer_id": customer.id}, created_by=user.id,
        )
        AuditLog.query.delete()
        db_session.commit()

        invoice_service.update_invoice(
            invoice.id, {"notes": "updated"}, user_id=user.id,
        )
        entry = AuditLog.query.filter_by(
            action="update", entity_type="invoice"
        ).first()
        assert entry is not None

    def test_add_line_item_logs_audit(self, app, db_session):
        _set_session(db_session, CustomerFactory, UserFactory)
        customer = CustomerFactory()
        user = UserFactory()
        db_session.commit()

        invoice = invoice_service.create_invoice(
            {"customer_id": customer.id}, created_by=user.id,
        )
        li = invoice_service.add_line_item(invoice.id, {
            "line_type": "service",
            "description": "Test Service",
            "quantity": 1,
            "unit_price": Decimal("75.00"),
        })
        entry = AuditLog.query.filter_by(
            action="create", entity_type="invoice_line_item"
        ).first()
        assert entry is not None
        assert entry.entity_id == li.id


# ── Helpers ───────────────────────────────────────────────────────────


def _get_csrf(client, url):
    """Extract a CSRF token from a GET response."""
    resp = client.get(url)
    html = resp.data.decode()
    # Look for the hidden csrf_token input
    import re
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if match:
        return match.group(1)
    # Fallback: look in meta tag
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    if match:
        return match.group(1)
    return ""
