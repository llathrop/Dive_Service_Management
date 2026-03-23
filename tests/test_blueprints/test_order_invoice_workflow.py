"""Tests for the order-invoice workflow: hide completed, cost preview,
auto-generate invoice on completion, $0 auto-pay, and last_service_date update.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.invoice import Invoice, invoice_orders
from app.services import invoice_service, order_service
from tests.factories import (
    AppliedServiceFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
)


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    """Bind Factory Boy factories to the test database session."""
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session
    ServiceOrderItemFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session
    AppliedServiceFactory._meta.sqlalchemy_session = db_session


# ======================================================================
# Hide completed orders
# ======================================================================


class TestHideCompletedOrders:
    """Feature #11: toggle to hide terminal-status orders from the list."""

    def test_hide_completed_true_excludes_terminal(self, admin_client, db_session):
        """With hide_completed=true, picked_up and cancelled orders are hidden."""
        customer = CustomerFactory()
        db_session.flush()
        active = ServiceOrderFactory(customer=customer, status="in_progress")
        picked_up = ServiceOrderFactory(customer=customer, status="picked_up")
        cancelled = ServiceOrderFactory(customer=customer, status="cancelled")
        db_session.commit()

        resp = admin_client.get("/orders/?hide_completed=true")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert active.order_number in html
        assert picked_up.order_number not in html
        assert cancelled.order_number not in html

    def test_hide_completed_false_shows_all(self, admin_client, db_session):
        """With hide_completed=false, all orders are shown."""
        customer = CustomerFactory()
        db_session.flush()
        active = ServiceOrderFactory(customer=customer, status="in_progress")
        picked_up = ServiceOrderFactory(customer=customer, status="picked_up")
        cancelled = ServiceOrderFactory(customer=customer, status="cancelled")
        db_session.commit()

        resp = admin_client.get("/orders/?hide_completed=false")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert active.order_number in html
        assert picked_up.order_number in html
        assert cancelled.order_number in html

    def test_hide_completed_default_is_true(self, admin_client, db_session):
        """Default (no parameter) hides terminal orders."""
        customer = CustomerFactory()
        db_session.flush()
        active = ServiceOrderFactory(customer=customer, status="in_progress")
        picked_up = ServiceOrderFactory(customer=customer, status="picked_up")
        db_session.commit()

        resp = admin_client.get("/orders/")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert active.order_number in html
        assert picked_up.order_number not in html


# ======================================================================
# Cost preview endpoint
# ======================================================================


class TestCostPreview:
    """Feature #12: cost preview for order-to-invoice generation."""

    def test_cost_preview_returns_correct_structure(self, admin_client, db_session):
        """GET /invoices/from-order/<id>/preview returns expected JSON keys."""
        customer = CustomerFactory()
        db_session.flush()
        order = ServiceOrderFactory(customer=customer, status="in_progress")
        db_session.flush()
        soi = ServiceOrderItemFactory(order=order)
        db_session.flush()
        AppliedServiceFactory(
            order_item=soi,
            service_name="Test Service",
            quantity=Decimal("1.00"),
            unit_price=Decimal("50.00"),
            line_total=Decimal("50.00"),
        )
        db_session.commit()

        resp = admin_client.get(f"/invoices/from-order/{order.id}/preview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "subtotal" in data
        assert "line_items" in data
        assert "rush_fee" in data
        assert "discount" in data
        assert "grand_total" in data
        assert len(data["line_items"]) == 1
        assert data["line_items"][0]["description"] == "Test Service"
        assert data["grand_total"] == "50.00"

    def test_cost_preview_not_found(self, admin_client):
        """Preview for non-existent order returns 404."""
        resp = admin_client.get("/invoices/from-order/99999/preview")
        assert resp.status_code == 404


# ======================================================================
# Generate invoice from order
# ======================================================================


class TestGenerateFromOrder:
    """Feature #12: generate invoice from a service order."""

    def test_generate_from_order_creates_invoice(self, db_session):
        """invoice_service.generate_from_order creates an invoice linked to the order."""
        customer = CustomerFactory()
        db_session.flush()
        order = ServiceOrderFactory(customer=customer, status="in_progress")
        db_session.flush()
        soi = ServiceOrderItemFactory(order=order)
        db_session.flush()
        AppliedServiceFactory(
            order_item=soi,
            service_name="Valve Service",
            quantity=Decimal("1.00"),
            unit_price=Decimal("75.00"),
            line_total=Decimal("75.00"),
        )
        db_session.commit()

        invoice = invoice_service.generate_from_order(order.id)
        assert invoice is not None
        assert invoice.invoice_number.startswith("INV-")
        assert invoice.total == Decimal("75.00")
        assert invoice.status == "draft"

        # Verify link via invoice_orders
        link = db_session.query(invoice_orders).filter(
            invoice_orders.c.order_id == order.id,
            invoice_orders.c.invoice_id == invoice.id,
        ).first()
        assert link is not None

    def test_zero_total_invoice_auto_marked_paid(self, db_session):
        """A $0.00 invoice is automatically marked as paid."""
        customer = CustomerFactory()
        db_session.flush()
        order = ServiceOrderFactory(customer=customer, status="in_progress")
        db_session.flush()
        ServiceOrderItemFactory(order=order)
        db_session.commit()

        invoice = invoice_service.generate_from_order(order.id)
        assert invoice.total == Decimal("0.00")
        assert invoice.status == "paid"
        assert invoice.paid_date == date.today()


# ======================================================================
# Completing an order
# ======================================================================


class TestOrderCompletion:
    """Features #8 and #12: auto-invoice and last_service_date on completion."""

    def test_completing_order_auto_generates_invoice(self, db_session):
        """Transitioning to 'completed' auto-generates an invoice."""
        customer = CustomerFactory()
        db_session.flush()
        order = ServiceOrderFactory(customer=customer, status="in_progress")
        db_session.flush()
        soi = ServiceOrderItemFactory(order=order)
        db_session.flush()
        AppliedServiceFactory(
            order_item=soi,
            service_name="O-Ring Replace",
            quantity=Decimal("1.00"),
            unit_price=Decimal("30.00"),
            line_total=Decimal("30.00"),
        )
        db_session.commit()

        result_order, success = order_service.change_status(order.id, "completed")
        assert success is True
        assert result_order.status == "completed"

        # Check invoice was created
        link = db_session.query(invoice_orders).filter(
            invoice_orders.c.order_id == order.id,
        ).first()
        assert link is not None

        invoice = db_session.get(Invoice, link.invoice_id)
        assert invoice is not None
        assert invoice.total == Decimal("30.00")

    def test_completing_order_updates_last_service_date(self, db_session):
        """Transitioning to 'completed' sets last_service_date on service items."""
        customer = CustomerFactory()
        db_session.flush()
        si = ServiceItemFactory(customer=customer, last_service_date=None)
        order = ServiceOrderFactory(customer=customer, status="in_progress")
        db_session.flush()
        ServiceOrderItemFactory(order=order, service_item=si)
        db_session.commit()

        _, success = order_service.change_status(order.id, "completed")
        assert success is True

        db_session.refresh(si)
        assert si.last_service_date == date.today()

    def test_completing_order_with_existing_invoice_no_duplicate(self, db_session):
        """If an invoice already exists for the order, no duplicate is created."""
        customer = CustomerFactory()
        db_session.flush()
        order = ServiceOrderFactory(customer=customer, status="in_progress")
        db_session.flush()
        soi = ServiceOrderItemFactory(order=order)
        db_session.flush()
        AppliedServiceFactory(
            order_item=soi,
            service_name="Hose Check",
            quantity=Decimal("1.00"),
            unit_price=Decimal("20.00"),
            line_total=Decimal("20.00"),
        )
        db_session.commit()

        # Pre-generate an invoice
        first_invoice = invoice_service.generate_from_order(order.id)
        first_id = first_invoice.id

        # Now complete the order
        _, success = order_service.change_status(order.id, "completed")
        assert success is True

        # Should still have only one invoice link
        links = db_session.query(invoice_orders).filter(
            invoice_orders.c.order_id == order.id,
        ).all()
        assert len(links) == 1
        assert links[0].invoice_id == first_id

    def test_invoice_failure_does_not_break_completion(self, db_session, monkeypatch):
        """If invoice generation raises, the status change still succeeds."""
        customer = CustomerFactory()
        db_session.flush()
        order = ServiceOrderFactory(customer=customer, status="in_progress")
        db_session.flush()
        ServiceOrderItemFactory(order=order)
        db_session.commit()

        # Monkey-patch generate_from_order to raise
        def boom(*args, **kwargs):
            raise RuntimeError("Invoice generation failed")

        monkeypatch.setattr(
            "app.services.invoice_service.generate_from_order", boom
        )

        result_order, success = order_service.change_status(order.id, "completed")
        assert success is True
        assert result_order.status == "completed"
        assert result_order.date_completed == date.today()
