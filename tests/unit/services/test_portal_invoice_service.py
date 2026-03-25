"""Unit tests for portal-safe invoice service helpers."""

from datetime import date
from decimal import Decimal

import pytest

from app.services import audit_service, portal_invoice_service
from tests.factories import (
    AuditLogFactory,
    CustomerFactory,
    InvoiceFactory,
    InvoiceLineItemFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    CustomerFactory._meta.sqlalchemy_session = db_session
    InvoiceFactory._meta.sqlalchemy_session = db_session
    InvoiceLineItemFactory._meta.sqlalchemy_session = db_session
    AuditLogFactory._meta.sqlalchemy_session = db_session


def _make_invoice(db_session, customer, **overrides):
    defaults = dict(
        invoice_number="INV-2026-10001",
        customer=customer,
        status="sent",
        issue_date=date(2026, 3, 1),
        due_date=date(2026, 3, 20),
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        balance_due=Decimal("100.00"),
    )
    defaults.update(overrides)
    return InvoiceFactory(**defaults)


class TestPortalInvoiceService:
    """Tests for portal-safe invoice service helpers."""

    def test_customer_invoice_view_sanitizes_labor_line_items(self, app, db_session):
        _set_session(db_session)
        customer = CustomerFactory(first_name="Portal", last_name="Customer")
        invoice = _make_invoice(
            db_session,
            customer,
            notes="Internal notes should not leak",
            customer_notes="Customer notes should not leak",
            external_id="EXT-123",
            external_system="quickbooks",
        )
        InvoiceLineItemFactory(
            invoice=invoice,
            line_type="labor",
            description="Technician Smith: Replace seals",
            quantity=Decimal("2.00"),
            unit_price=Decimal("50.00"),
            line_total=Decimal("100.00"),
        )

        view = portal_invoice_service.get_customer_invoice_view(customer.id, invoice.id)

        assert view is not None
        assert view["payment_context"]["provider_code"] == "manual"
        assert view["line_items"][0]["description"] == "Labor"
        assert view["line_items"][0]["line_total"] == Decimal("100.00")

    def test_customer_invoice_view_rejects_foreign_customer(self, app, db_session):
        _set_session(db_session)
        owner = CustomerFactory(first_name="Owner", last_name="Customer")
        stranger = CustomerFactory(first_name="Other", last_name="Customer")
        invoice = _make_invoice(db_session, owner)

        assert portal_invoice_service.get_customer_invoice_view(stranger.id, invoice.id) is None

    def test_status_history_uses_invoice_audit_trail(self, app, db_session):
        _set_session(db_session)
        customer = CustomerFactory(first_name="History", last_name="Target")
        invoice = _make_invoice(db_session, customer)

        audit_service.log_action(
            action="status_change",
            entity_type="invoice",
            entity_id=invoice.id,
            field_name="status",
            old_value="draft",
            new_value="sent",
        )

        history = portal_invoice_service.get_customer_invoice_status_history(
            customer.id,
            invoice.id,
        )
        assert history is not None
        assert len(history) == 1
        assert history[0].new_value == "sent"

