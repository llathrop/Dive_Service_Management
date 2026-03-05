"""Unit tests for the Invoice, InvoiceLineItem, and Payment models.

Tests cover creation, defaults, validation constants, properties,
recalculate_totals, relationships, and representation.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.invoice import (
    TERMINAL_STATUSES,
    VALID_LINE_TYPES,
    VALID_STATUSES,
    Invoice,
    InvoiceLineItem,
)
from app.models.payment import (
    VALID_PAYMENT_METHODS,
    VALID_PAYMENT_TYPES,
    Payment,
)
from tests.factories import (
    CustomerFactory,
    InvoiceFactory,
    InvoiceLineItemFactory,
    PaymentFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    InvoiceFactory._meta.sqlalchemy_session = db_session
    InvoiceLineItemFactory._meta.sqlalchemy_session = db_session
    PaymentFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session


# =========================================================================
# Invoice creation
# =========================================================================


class TestInvoiceCreation:
    """Tests for basic invoice creation and persistence."""

    def test_create_invoice(self, app, db_session):
        """An invoice persists all required fields correctly."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="John", last_name="Diver")
        invoice = InvoiceFactory(
            invoice_number="INV-2026-00001",
            customer=customer,
            status="draft",
            issue_date=date(2026, 3, 1),
            subtotal=Decimal("200.00"),
            total=Decimal("200.00"),
            balance_due=Decimal("200.00"),
        )

        fetched = db_session.get(Invoice, invoice.id)
        assert fetched is not None
        assert fetched.invoice_number == "INV-2026-00001"
        assert fetched.customer_id == customer.id
        assert fetched.status == "draft"
        assert fetched.issue_date == date(2026, 3, 1)
        assert fetched.subtotal == Decimal("200.00")
        assert fetched.total == Decimal("200.00")
        assert fetched.balance_due == Decimal("200.00")

    def test_invoice_defaults(self, app, db_session):
        """Default values are applied correctly on a minimal invoice."""
        _set_session(db_session)
        customer = CustomerFactory()
        invoice = Invoice(
            invoice_number="INV-2026-00099",
            customer_id=customer.id,
            issue_date=date.today(),
        )
        db_session.add(invoice)
        db_session.commit()

        fetched = db_session.get(Invoice, invoice.id)
        assert fetched.status == "draft"
        assert fetched.amount_paid == Decimal("0.00")


# =========================================================================
# Invoice constants
# =========================================================================


class TestInvoiceConstants:
    """Tests for validation constants."""

    def test_valid_statuses(self, app):
        """VALID_STATUSES contains all expected invoice statuses."""
        expected = [
            "draft",
            "sent",
            "viewed",
            "partially_paid",
            "paid",
            "overdue",
            "void",
            "refunded",
        ]
        assert VALID_STATUSES == expected

    def test_terminal_statuses(self, app):
        """TERMINAL_STATUSES contains the statuses treated as final."""
        expected = ["paid", "void", "refunded"]
        assert TERMINAL_STATUSES == expected

    def test_valid_line_types(self, app):
        """VALID_LINE_TYPES contains all expected line item types."""
        expected = ["service", "labor", "part", "fee", "discount", "other"]
        assert VALID_LINE_TYPES == expected


# =========================================================================
# Invoice properties
# =========================================================================


class TestInvoiceProperties:
    """Tests for computed properties."""

    def test_display_status(self, app, db_session):
        """display_status converts underscored status to title case."""
        _set_session(db_session)
        invoice = InvoiceFactory(status="partially_paid")
        assert invoice.display_status == "Partially Paid"

    def test_display_status_simple(self, app, db_session):
        """display_status works for simple single-word statuses."""
        _set_session(db_session)
        invoice = InvoiceFactory(status="draft")
        assert invoice.display_status == "Draft"

    def test_is_not_overdue_when_no_due_date(self, app, db_session):
        """An invoice without a due_date is not overdue."""
        _set_session(db_session)
        invoice = InvoiceFactory(
            status="sent",
            due_date=None,
        )
        assert invoice.is_overdue is False

    def test_is_not_overdue_when_terminal_status(self, app, db_session):
        """An invoice in a terminal status is not overdue even with a past due_date."""
        _set_session(db_session)
        invoice = InvoiceFactory(
            status="paid",
            due_date=date.today() - timedelta(days=1),
        )
        assert invoice.is_overdue is False

    def test_is_not_overdue_when_void(self, app, db_session):
        """A voided invoice is not overdue even with a past due_date."""
        _set_session(db_session)
        invoice = InvoiceFactory(
            status="void",
            due_date=date.today() - timedelta(days=1),
        )
        assert invoice.is_overdue is False

    def test_is_overdue_when_past_due(self, app, db_session):
        """An invoice is overdue when due_date is in the past and not terminal."""
        _set_session(db_session)
        invoice = InvoiceFactory(
            status="sent",
            due_date=date.today() - timedelta(days=1),
        )
        assert invoice.is_overdue is True

    def test_is_not_overdue_when_future_date(self, app, db_session):
        """An invoice with a future due_date is not overdue."""
        _set_session(db_session)
        invoice = InvoiceFactory(
            status="sent",
            due_date=date.today() + timedelta(days=7),
        )
        assert invoice.is_overdue is False


# =========================================================================
# recalculate_totals
# =========================================================================


class TestInvoiceRecalculateTotals:
    """Tests for recalculate_totals method."""

    def test_recalculate_totals_with_line_items(self, app, db_session):
        """recalculate_totals sums line items and computes balance_due."""
        _set_session(db_session)
        invoice = InvoiceFactory(
            subtotal=Decimal("0.00"),
            total=Decimal("0.00"),
            balance_due=Decimal("0.00"),
            amount_paid=Decimal("0.00"),
        )
        InvoiceLineItemFactory(
            invoice=invoice,
            quantity=Decimal("2.00"),
            unit_price=Decimal("50.00"),
            line_total=Decimal("100.00"),
        )
        InvoiceLineItemFactory(
            invoice=invoice,
            quantity=Decimal("1.00"),
            unit_price=Decimal("75.00"),
            line_total=Decimal("75.00"),
        )
        db_session.flush()

        invoice.recalculate_totals()
        db_session.commit()

        assert invoice.subtotal == Decimal("175.00")
        assert invoice.total == Decimal("175.00")
        assert invoice.balance_due == Decimal("175.00")

    def test_recalculate_totals_empty(self, app, db_session):
        """recalculate_totals with no line items results in zeros."""
        _set_session(db_session)
        invoice = InvoiceFactory(
            subtotal=Decimal("100.00"),
            total=Decimal("100.00"),
            balance_due=Decimal("100.00"),
            amount_paid=Decimal("0.00"),
        )

        invoice.recalculate_totals()
        db_session.commit()

        assert invoice.subtotal == Decimal("0")
        assert invoice.total == Decimal("0")
        assert invoice.balance_due == Decimal("0")


# =========================================================================
# Invoice relationships
# =========================================================================


class TestInvoiceRelationships:
    """Tests for model relationships."""

    def test_customer_relationship(self, app, db_session):
        """An invoice links to its customer via the relationship."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Reef", last_name="Diver")
        invoice = InvoiceFactory(customer=customer)

        assert invoice.customer.id == customer.id
        assert invoice.customer.first_name == "Reef"

    def test_line_items_relationship(self, app, db_session):
        """An invoice can have multiple line items."""
        _set_session(db_session)
        invoice = InvoiceFactory()
        item1 = InvoiceLineItemFactory(invoice=invoice)
        item2 = InvoiceLineItemFactory(invoice=invoice)

        items = invoice.line_items.all()
        assert len(items) == 2
        item_ids = {i.id for i in items}
        assert item1.id in item_ids
        assert item2.id in item_ids

    def test_payments_relationship(self, app, db_session):
        """An invoice can have multiple payments."""
        _set_session(db_session)
        invoice = InvoiceFactory()
        p1 = PaymentFactory(invoice=invoice, amount=Decimal("25.00"))
        p2 = PaymentFactory(invoice=invoice, amount=Decimal("30.00"))

        payments = invoice.payments.all()
        assert len(payments) == 2
        payment_ids = {p.id for p in payments}
        assert p1.id in payment_ids
        assert p2.id in payment_ids


# =========================================================================
# Invoice __repr__
# =========================================================================


class TestInvoiceRepr:
    """Tests for __repr__."""

    def test_repr(self, app, db_session):
        """__repr__ includes id and invoice_number."""
        _set_session(db_session)
        invoice = InvoiceFactory(invoice_number="INV-2026-00042")
        expected = f"<Invoice {invoice.id} 'INV-2026-00042'>"
        assert repr(invoice) == expected


# =========================================================================
# InvoiceLineItem creation
# =========================================================================


class TestInvoiceLineItemCreation:
    """Tests for basic InvoiceLineItem creation."""

    def test_create_line_item(self, app, db_session):
        """A line item persists all required fields correctly."""
        _set_session(db_session)
        invoice = InvoiceFactory()
        line_item = InvoiceLineItemFactory(
            invoice=invoice,
            line_type="service",
            description="Regulator Annual Service",
            quantity=Decimal("1.00"),
            unit_price=Decimal("150.00"),
            line_total=Decimal("150.00"),
        )

        fetched = db_session.get(InvoiceLineItem, line_item.id)
        assert fetched is not None
        assert fetched.invoice_id == invoice.id
        assert fetched.line_type == "service"
        assert fetched.description == "Regulator Annual Service"
        assert fetched.quantity == Decimal("1.00")
        assert fetched.unit_price == Decimal("150.00")
        assert fetched.line_total == Decimal("150.00")

    def test_line_item_invoice_relationship(self, app, db_session):
        """A line item links back to its invoice."""
        _set_session(db_session)
        invoice = InvoiceFactory(invoice_number="INV-2026-00050")
        line_item = InvoiceLineItemFactory(invoice=invoice)

        assert line_item.invoice.id == invoice.id
        assert line_item.invoice.invoice_number == "INV-2026-00050"


# =========================================================================
# Payment creation
# =========================================================================


class TestPaymentCreation:
    """Tests for basic Payment creation."""

    def test_create_payment(self, app, db_session):
        """A payment persists all required fields correctly."""
        _set_session(db_session)
        invoice = InvoiceFactory()
        payment = PaymentFactory(
            invoice=invoice,
            payment_type="payment",
            amount=Decimal("75.00"),
            payment_date=date(2026, 3, 1),
            payment_method="credit_card",
        )

        fetched = db_session.get(Payment, payment.id)
        assert fetched is not None
        assert fetched.invoice_id == invoice.id
        assert fetched.payment_type == "payment"
        assert fetched.amount == Decimal("75.00")
        assert fetched.payment_date == date(2026, 3, 1)
        assert fetched.payment_method == "credit_card"

    def test_payment_invoice_relationship(self, app, db_session):
        """A payment links back to its invoice."""
        _set_session(db_session)
        invoice = InvoiceFactory(invoice_number="INV-2026-00060")
        payment = PaymentFactory(invoice=invoice)

        assert payment.invoice.id == invoice.id
        assert payment.invoice.invoice_number == "INV-2026-00060"


# =========================================================================
# Payment constants
# =========================================================================


class TestPaymentConstants:
    """Tests for payment validation constants."""

    def test_valid_payment_types(self, app):
        """VALID_PAYMENT_TYPES contains all expected payment types."""
        expected = ["payment", "deposit", "refund"]
        assert VALID_PAYMENT_TYPES == expected

    def test_valid_payment_methods(self, app):
        """VALID_PAYMENT_METHODS contains all expected payment methods."""
        expected = [
            "cash",
            "check",
            "credit_card",
            "debit_card",
            "bank_transfer",
            "other",
        ]
        assert VALID_PAYMENT_METHODS == expected
