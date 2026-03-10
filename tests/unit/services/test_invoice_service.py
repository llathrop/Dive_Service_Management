"""Unit tests for the invoice service layer.

Tests cover paginated listing, search, filtering, CRUD operations,
invoice number generation, line item management, payment recording,
and invoice generation from service orders.
"""

import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.applied_service import AppliedService
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.labor import LaborEntry
from app.models.parts_used import PartUsed
from app.models.payment import Payment
from app.models.service_item import ServiceItem
from app.models.service_order import ServiceOrder
from app.models.service_order_item import ServiceOrderItem
from app.models.user import User
from app.services import invoice_service

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_customer(db_session, **kwargs):
    """Create and persist a Customer with sensible defaults."""
    defaults = {
        "customer_type": "individual",
        "first_name": "Test",
        "last_name": "Diver",
    }
    defaults.update(kwargs)
    customer = Customer(**defaults)
    db_session.add(customer)
    db_session.commit()
    return customer


def _make_invoice(db_session, customer=None, **kwargs):
    """Create and persist an Invoice with sensible defaults."""
    if customer is None:
        customer = _make_customer(db_session)
    defaults = {
        "invoice_number": kwargs.pop("invoice_number", f"INV-2026-{uuid.uuid4().hex[:5]}"),
        "customer_id": customer.id,
        "status": "draft",
        "issue_date": date.today(),
        "subtotal": Decimal("0.00"),
        "total": Decimal("0.00"),
        "balance_due": Decimal("0.00"),
    }
    defaults.update(kwargs)
    invoice = Invoice(**defaults)
    db_session.add(invoice)
    db_session.commit()
    return invoice


def _make_line_item(db_session, invoice=None, **kwargs):
    """Create and persist an InvoiceLineItem."""
    if invoice is None:
        invoice = _make_invoice(db_session)
    defaults = {
        "invoice_id": invoice.id,
        "line_type": "service",
        "description": "Test Service",
        "quantity": Decimal("1.00"),
        "unit_price": Decimal("100.00"),
        "line_total": Decimal("100.00"),
    }
    defaults.update(kwargs)
    item = InvoiceLineItem(**defaults)
    db_session.add(item)
    db_session.commit()
    return item


def _make_user(db_session, **kwargs):
    """Create and persist a User."""
    defaults = {
        "username": kwargs.pop("username", f"user_{uuid.uuid4().hex[:8]}"),
        "email": kwargs.pop("email", f"{uuid.uuid4().hex[:8]}@example.com"),
        "first_name": "Tech",
        "last_name": "User",
        "password": "password",
        "active": True,
        "fs_uniquifier": str(uuid.uuid4()),
    }
    defaults.update(kwargs)
    user = User(**defaults)
    db_session.add(user)
    db_session.commit()
    return user


def _make_order(db_session, customer=None, **kwargs):
    """Create and persist a ServiceOrder with sensible defaults."""
    if customer is None:
        customer = _make_customer(db_session)
    defaults = {
        "order_number": kwargs.pop("order_number", f"SO-2026-{uuid.uuid4().hex[:5]}"),
        "customer_id": customer.id,
        "status": "intake",
        "priority": "normal",
        "date_received": date.today(),
    }
    defaults.update(kwargs)
    order = ServiceOrder(**defaults)
    db_session.add(order)
    db_session.commit()
    return order


def _make_service_item(db_session, **kwargs):
    """Create and persist a ServiceItem."""
    defaults = {
        "name": "Test Regulator",
        "item_category": "Regulator",
        "serviceability": "serviceable",
    }
    defaults.update(kwargs)
    item = ServiceItem(**defaults)
    db_session.add(item)
    db_session.commit()
    return item


def _make_order_item(db_session, order=None, service_item=None, **kwargs):
    """Create and persist a ServiceOrderItem."""
    if order is None:
        order = _make_order(db_session)
    if service_item is None:
        service_item = _make_service_item(db_session)
    defaults = {
        "order_id": order.id,
        "service_item_id": service_item.id,
    }
    defaults.update(kwargs)
    oi = ServiceOrderItem(**defaults)
    db_session.add(oi)
    db_session.commit()
    return oi


def _make_inventory_item(db_session, **kwargs):
    """Create and persist an InventoryItem."""
    defaults = {
        "sku": kwargs.pop("sku", f"SKU-{uuid.uuid4().hex[:5]}"),
        "name": "O-Ring",
        "category": "Seals",
        "purchase_cost": Decimal("2.00"),
        "resale_price": Decimal("5.00"),
        "quantity_in_stock": 100,
        "reorder_level": 10,
        "unit_of_measure": "each",
        "is_active": True,
    }
    defaults.update(kwargs)
    item = InventoryItem(**defaults)
    db_session.add(item)
    db_session.commit()
    return item


# =========================================================================
# get_invoices
# =========================================================================


class TestGetInvoices:
    """Tests for get_invoices()."""

    def test_get_invoices_empty(self, app, db_session):
        """Returns empty pagination when no invoices exist."""
        result = invoice_service.get_invoices(page=1, per_page=25)
        assert result.total == 0
        assert len(result.items) == 0

    def test_get_invoices_with_data(self, app, db_session):
        """Returns invoices when they exist."""
        customer = _make_customer(db_session)
        _make_invoice(db_session, customer=customer, invoice_number="INV-2026-00001")
        _make_invoice(db_session, customer=customer, invoice_number="INV-2026-00002")

        result = invoice_service.get_invoices(page=1, per_page=25)
        assert result.total == 2
        assert len(result.items) == 2

    def test_get_invoices_pagination(self, app, db_session):
        """Pagination limits the number of results per page."""
        customer = _make_customer(db_session)
        for i in range(5):
            _make_invoice(
                db_session, customer=customer,
                invoice_number=f"INV-2026-{i+1:05d}",
            )

        result = invoice_service.get_invoices(page=1, per_page=2)
        assert result.total == 5
        assert len(result.items) == 2

    def test_get_invoices_filter_status(self, app, db_session):
        """Filtering by status returns only matching invoices."""
        customer = _make_customer(db_session)
        _make_invoice(db_session, customer=customer, invoice_number="INV-2026-00010", status="draft")
        _make_invoice(db_session, customer=customer, invoice_number="INV-2026-00011", status="sent")

        result = invoice_service.get_invoices(status="sent")
        assert result.total == 1
        assert result.items[0].status == "sent"

    def test_get_invoices_search(self, app, db_session):
        """Search by invoice_number returns matching results."""
        customer = _make_customer(db_session)
        _make_invoice(db_session, customer=customer, invoice_number="INV-2026-00100")
        _make_invoice(db_session, customer=customer, invoice_number="INV-2026-00200")

        result = invoice_service.get_invoices(search="00100")
        assert result.total == 1
        assert result.items[0].invoice_number == "INV-2026-00100"

    def test_get_invoices_date_range(self, app, db_session):
        """Filtering by date range returns invoices in range."""
        customer = _make_customer(db_session)
        _make_invoice(
            db_session, customer=customer,
            invoice_number="INV-2026-00300",
            issue_date=date(2026, 1, 15),
        )
        _make_invoice(
            db_session, customer=customer,
            invoice_number="INV-2026-00301",
            issue_date=date(2026, 3, 15),
        )

        result = invoice_service.get_invoices(
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
        )
        assert result.total == 1
        assert result.items[0].invoice_number == "INV-2026-00301"

    def test_get_invoices_overdue_only(self, app, db_session):
        """overdue_only returns only invoices past their due date."""
        customer = _make_customer(db_session)
        _make_invoice(
            db_session, customer=customer,
            invoice_number="INV-2026-00400",
            status="sent",
            due_date=date.today() - timedelta(days=5),
        )
        _make_invoice(
            db_session, customer=customer,
            invoice_number="INV-2026-00401",
            status="sent",
            due_date=date.today() + timedelta(days=5),
        )

        result = invoice_service.get_invoices(overdue_only=True)
        assert result.total == 1
        assert result.items[0].invoice_number == "INV-2026-00400"

    def test_get_invoices_sorting(self, app, db_session):
        """Sorting by invoice_number ascending returns correct order."""
        customer = _make_customer(db_session)
        _make_invoice(db_session, customer=customer, invoice_number="INV-2026-00502")
        _make_invoice(db_session, customer=customer, invoice_number="INV-2026-00501")

        result = invoice_service.get_invoices(sort="invoice_number", order="asc")
        numbers = [inv.invoice_number for inv in result.items]
        assert numbers == ["INV-2026-00501", "INV-2026-00502"]


# =========================================================================
# get_invoice
# =========================================================================


class TestGetInvoice:
    """Tests for get_invoice()."""

    def test_get_invoice_found(self, app, db_session):
        """get_invoice() returns the correct invoice by ID."""
        invoice = _make_invoice(db_session)
        result = invoice_service.get_invoice(invoice.id)
        assert result is not None
        assert result.id == invoice.id

    def test_get_invoice_not_found(self, app, db_session):
        """get_invoice() returns None for a non-existent ID."""
        result = invoice_service.get_invoice(99999)
        assert result is None


# =========================================================================
# create_invoice
# =========================================================================


class TestCreateInvoice:
    """Tests for create_invoice()."""

    def test_create_invoice(self, app, db_session):
        """create_invoice() persists an invoice with auto-generated number."""
        customer = _make_customer(db_session)
        data = {
            "customer_id": customer.id,
            "issue_date": date.today(),
            "notes": "Test invoice",
        }
        invoice = invoice_service.create_invoice(data)

        assert invoice.id is not None
        assert invoice.customer_id == customer.id
        assert invoice.notes == "Test invoice"
        assert invoice.status == "draft"

        # Verify persistence
        fetched = db_session.get(Invoice, invoice.id)
        assert fetched is not None

    def test_create_invoice_generates_number(self, app, db_session):
        """create_invoice() generates an invoice_number in INV-YYYY-NNNNN format."""
        customer = _make_customer(db_session)
        data = {"customer_id": customer.id, "issue_date": date.today()}
        invoice = invoice_service.create_invoice(data)

        pattern = r"^INV-\d{4}-\d{5}$"
        assert re.match(pattern, invoice.invoice_number), (
            f"Invoice number {invoice.invoice_number!r} does not match pattern"
        )


# =========================================================================
# update_invoice
# =========================================================================


class TestUpdateInvoice:
    """Tests for update_invoice()."""

    def test_update_invoice(self, app, db_session):
        """update_invoice() updates specified fields (but not status)."""
        invoice = _make_invoice(db_session)

        updated = invoice_service.update_invoice(
            invoice.id,
            {"notes": "Updated notes"},
        )

        assert updated is not None
        assert updated.notes == "Updated notes"
        assert updated.status == "draft"  # status unchanged — use change_status()

    def test_update_invoice_recalculates_totals(self, app, db_session):
        """update_invoice() recalculates totals when tax_rate changes."""
        invoice = _make_invoice(db_session)
        _make_line_item(
            db_session, invoice=invoice,
            line_total=Decimal("100.00"),
        )

        updated = invoice_service.update_invoice(
            invoice.id,
            {"tax_rate": Decimal("0.1000")},
        )

        assert updated is not None
        assert updated.subtotal == Decimal("100.00")
        assert updated.tax_amount == Decimal("10.0000")

    def test_update_invoice_not_found(self, app, db_session):
        """update_invoice() returns None for a non-existent ID."""
        result = invoice_service.update_invoice(99999, {"notes": "test"})
        assert result is None


# =========================================================================
# void_invoice
# =========================================================================


class TestVoidInvoice:
    """Tests for void_invoice()."""

    def test_void_invoice(self, app, db_session):
        """void_invoice() sets the status to 'void'."""
        invoice = _make_invoice(db_session, status="sent")

        result = invoice_service.void_invoice(invoice.id)

        assert result is not None
        assert result.status == "void"

    def test_void_invoice_not_found(self, app, db_session):
        """void_invoice() returns None for a non-existent ID."""
        result = invoice_service.void_invoice(99999)
        assert result is None


# =========================================================================
# generate_invoice_number
# =========================================================================


class TestGenerateInvoiceNumber:
    """Tests for generate_invoice_number()."""

    def test_generate_invoice_number_first(self, app, db_session):
        """First invoice number for the year is INV-YYYY-00001."""
        number = invoice_service.generate_invoice_number()
        current_year = date.today().year
        assert number == f"INV-{current_year}-00001"

    def test_generate_invoice_number_increments(self, app, db_session):
        """Subsequent invoice numbers increment the sequence."""
        customer = _make_customer(db_session)
        current_year = date.today().year
        _make_invoice(
            db_session, customer=customer,
            invoice_number=f"INV-{current_year}-00005",
        )

        number = invoice_service.generate_invoice_number()
        assert number == f"INV-{current_year}-00006"

    def test_generate_invoice_number_format(self, app, db_session):
        """Generated number matches the INV-YYYY-NNNNN format."""
        number = invoice_service.generate_invoice_number()
        pattern = r"^INV-\d{4}-\d{5}$"
        assert re.match(pattern, number), (
            f"Invoice number {number!r} does not match pattern"
        )


# =========================================================================
# Line Items
# =========================================================================


class TestLineItems:
    """Tests for add_line_item and remove_line_item."""

    def test_add_line_item(self, app, db_session):
        """add_line_item() creates a line item and recalculates totals."""
        invoice = _make_invoice(db_session)

        data = {
            "line_type": "service",
            "description": "Regulator Annual Service",
            "quantity": Decimal("1.00"),
            "unit_price": Decimal("150.00"),
        }
        item = invoice_service.add_line_item(invoice.id, data)

        assert item is not None
        assert item.id is not None
        assert item.invoice_id == invoice.id
        assert item.description == "Regulator Annual Service"
        assert item.line_total == Decimal("150.00")

        # Totals should be recalculated
        db_session.refresh(invoice)
        assert invoice.subtotal == Decimal("150.00")

    def test_add_line_item_invoice_not_found(self, app, db_session):
        """add_line_item() returns None for non-existent invoice."""
        data = {
            "line_type": "service",
            "description": "Test",
            "quantity": Decimal("1.00"),
            "unit_price": Decimal("50.00"),
        }
        result = invoice_service.add_line_item(99999, data)
        assert result is None

    def test_remove_line_item(self, app, db_session):
        """remove_line_item() deletes the item and recalculates totals."""
        invoice = _make_invoice(db_session)
        item = _make_line_item(
            db_session, invoice=invoice,
            line_total=Decimal("100.00"),
        )
        # Recalculate so invoice has correct totals
        invoice.recalculate_totals()
        db_session.commit()
        assert invoice.subtotal == Decimal("100.00")

        result = invoice_service.remove_line_item(item.id)

        assert result is True
        assert db_session.get(InvoiceLineItem, item.id) is None

        # Totals should be recalculated to zero
        db_session.refresh(invoice)
        assert invoice.subtotal == Decimal("0")

    def test_remove_nonexistent_line_item(self, app, db_session):
        """remove_line_item() returns False for a non-existent ID."""
        result = invoice_service.remove_line_item(99999)
        assert result is False


# =========================================================================
# Payments
# =========================================================================


class TestPayments:
    """Tests for record_payment and get_payments."""

    def test_record_payment(self, app, db_session):
        """record_payment() creates a payment and updates invoice."""
        invoice = _make_invoice(
            db_session,
            total=Decimal("200.00"),
            balance_due=Decimal("200.00"),
        )

        data = {
            "payment_type": "payment",
            "amount": Decimal("100.00"),
            "payment_date": date.today(),
            "payment_method": "cash",
        }
        payment = invoice_service.record_payment(invoice.id, data)

        assert payment is not None
        assert payment.id is not None
        assert payment.amount == Decimal("100.00")

        # Invoice should be updated
        db_session.refresh(invoice)
        assert invoice.amount_paid == Decimal("100.00")
        assert invoice.balance_due == Decimal("100.00")
        assert invoice.status == "partially_paid"

    def test_record_payment_fully_paid(self, app, db_session):
        """record_payment() transitions to 'paid' when fully paid."""
        invoice = _make_invoice(
            db_session,
            total=Decimal("100.00"),
            balance_due=Decimal("100.00"),
        )

        data = {
            "payment_type": "payment",
            "amount": Decimal("100.00"),
            "payment_date": date.today(),
            "payment_method": "credit_card",
        }
        invoice_service.record_payment(invoice.id, data)

        db_session.refresh(invoice)
        assert invoice.status == "paid"
        assert invoice.balance_due <= Decimal("0.00")
        assert invoice.paid_date == date.today()

    def test_record_payment_partially_paid(self, app, db_session):
        """record_payment() transitions to 'partially_paid' when partially paid."""
        invoice = _make_invoice(
            db_session,
            total=Decimal("200.00"),
            balance_due=Decimal("200.00"),
        )

        data = {
            "payment_type": "payment",
            "amount": Decimal("50.00"),
            "payment_date": date.today(),
            "payment_method": "cash",
        }
        invoice_service.record_payment(invoice.id, data)

        db_session.refresh(invoice)
        assert invoice.status == "partially_paid"
        assert invoice.amount_paid == Decimal("50.00")
        assert invoice.balance_due == Decimal("150.00")

    def test_record_payment_invoice_not_found(self, app, db_session):
        """record_payment() returns None for non-existent invoice."""
        data = {
            "payment_type": "payment",
            "amount": Decimal("50.00"),
            "payment_date": date.today(),
            "payment_method": "cash",
        }
        result = invoice_service.record_payment(99999, data)
        assert result is None

    def test_get_payments(self, app, db_session):
        """get_payments() returns payments for an invoice ordered by date."""
        invoice = _make_invoice(db_session)

        p1 = Payment(
            invoice_id=invoice.id,
            payment_type="payment",
            amount=Decimal("50.00"),
            payment_date=date(2026, 3, 1),
            payment_method="cash",
        )
        p2 = Payment(
            invoice_id=invoice.id,
            payment_type="payment",
            amount=Decimal("25.00"),
            payment_date=date(2026, 3, 5),
            payment_method="check",
        )
        db_session.add_all([p1, p2])
        db_session.commit()

        payments = invoice_service.get_payments(invoice.id)
        assert len(payments) == 2
        assert payments[0].payment_date <= payments[1].payment_date

    def test_get_payments_empty(self, app, db_session):
        """get_payments() returns empty list when no payments exist."""
        invoice = _make_invoice(db_session)
        payments = invoice_service.get_payments(invoice.id)
        assert payments == []


# =========================================================================
# Generate from Order
# =========================================================================


class TestGenerateFromOrder:
    """Tests for generate_from_order()."""

    def test_generate_from_order_basic(self, app, db_session):
        """generate_from_order() creates an invoice from a service order."""
        customer = _make_customer(db_session)
        order = _make_order(db_session, customer=customer)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)

        # Add an applied service
        applied = AppliedService(
            service_order_item_id=oi.id,
            service_name="Annual Service",
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            discount_percent=Decimal("0.00"),
            line_total=Decimal("100.00"),
        )
        db_session.add(applied)
        db_session.commit()

        invoice = invoice_service.generate_from_order(order.id)

        assert invoice is not None
        assert invoice.id is not None
        assert invoice.customer_id == customer.id
        assert invoice.status == "draft"
        assert re.match(r"^INV-\d{4}-\d{5}$", invoice.invoice_number)

        # Check line items
        items = invoice.line_items.all()
        assert len(items) == 1
        assert items[0].line_type == "service"
        assert items[0].description == "Annual Service"

    def test_generate_from_order_with_parts(self, app, db_session):
        """generate_from_order() includes non-auto-deducted parts."""
        customer = _make_customer(db_session)
        order = _make_order(db_session, customer=customer)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        inv_item = _make_inventory_item(db_session)

        # Add a manually added part (non-auto-deducted)
        part = PartUsed(
            service_order_item_id=oi.id,
            inventory_item_id=inv_item.id,
            quantity=Decimal("2"),
            unit_cost_at_use=Decimal("5.00"),
            unit_price_at_use=Decimal("10.00"),
            is_auto_deducted=False,
        )
        db_session.add(part)
        db_session.commit()

        invoice = invoice_service.generate_from_order(order.id)

        items = invoice.line_items.all()
        part_items = [i for i in items if i.line_type == "part"]
        assert len(part_items) == 1
        assert part_items[0].quantity == Decimal("2")

    def test_generate_from_order_excludes_auto_deducted_parts(self, app, db_session):
        """generate_from_order() excludes auto-deducted parts."""
        customer = _make_customer(db_session)
        order = _make_order(db_session, customer=customer)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        inv_item = _make_inventory_item(db_session)

        # Auto-deducted part
        part = PartUsed(
            service_order_item_id=oi.id,
            inventory_item_id=inv_item.id,
            quantity=Decimal("1"),
            unit_cost_at_use=Decimal("5.00"),
            unit_price_at_use=Decimal("10.00"),
            is_auto_deducted=True,
        )
        db_session.add(part)
        db_session.commit()

        invoice = invoice_service.generate_from_order(order.id)

        items = invoice.line_items.all()
        part_items = [i for i in items if i.line_type == "part"]
        assert len(part_items) == 0

    def test_generate_from_order_with_labor(self, app, db_session):
        """generate_from_order() includes labor entries."""
        customer = _make_customer(db_session)
        order = _make_order(db_session, customer=customer)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        tech = _make_user(db_session, first_name="Jane", last_name="Tech")

        labor = LaborEntry(
            service_order_item_id=oi.id,
            tech_id=tech.id,
            hours=Decimal("2.00"),
            hourly_rate=Decimal("75.00"),
            description="Seal replacement",
            work_date=date.today(),
        )
        db_session.add(labor)
        db_session.commit()

        invoice = invoice_service.generate_from_order(order.id)

        items = invoice.line_items.all()
        labor_items = [i for i in items if i.line_type == "labor"]
        assert len(labor_items) == 1
        assert labor_items[0].quantity == Decimal("2.00")
        assert labor_items[0].unit_price == Decimal("75.00")

    def test_generate_from_order_with_rush_fee(self, app, db_session):
        """generate_from_order() includes rush fee as a line item."""
        customer = _make_customer(db_session)
        order = _make_order(
            db_session, customer=customer,
            rush_fee=Decimal("50.00"),
        )
        si = _make_service_item(db_session)
        _make_order_item(db_session, order=order, service_item=si)

        invoice = invoice_service.generate_from_order(order.id)

        items = invoice.line_items.all()
        fee_items = [i for i in items if i.line_type == "fee"]
        assert len(fee_items) == 1
        assert fee_items[0].description == "Rush Fee"
        assert fee_items[0].line_total == Decimal("50.00")

    def test_generate_from_order_with_discount(self, app, db_session):
        """generate_from_order() includes discount as a negative line item."""
        customer = _make_customer(db_session)
        order = _make_order(
            db_session, customer=customer,
            discount_amount=Decimal("20.00"),
        )
        si = _make_service_item(db_session)
        _make_order_item(db_session, order=order, service_item=si)

        invoice = invoice_service.generate_from_order(order.id)

        items = invoice.line_items.all()
        discount_items = [i for i in items if i.line_type == "discount"]
        assert len(discount_items) == 1
        assert discount_items[0].description == "Discount"
        assert discount_items[0].line_total == Decimal("-20.00")

    def test_generate_from_order_not_found(self, app, db_session):
        """generate_from_order() raises ValueError for non-existent order."""
        with pytest.raises(ValueError, match="not found"):
            invoice_service.generate_from_order(99999)

    def test_generate_from_order_links_order(self, app, db_session):
        """generate_from_order() links the order to the invoice."""
        customer = _make_customer(db_session)
        order = _make_order(db_session, customer=customer)
        si = _make_service_item(db_session)
        _make_order_item(db_session, order=order, service_item=si)

        invoice = invoice_service.generate_from_order(order.id)

        assert order in invoice.orders

    def test_generate_from_order_full(self, app, db_session):
        """generate_from_order() with services, parts, and labor creates correct line items."""
        customer = _make_customer(db_session)
        order = _make_order(db_session, customer=customer)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        tech = _make_user(db_session)
        inv_item = _make_inventory_item(db_session)

        # Applied service
        applied = AppliedService(
            service_order_item_id=oi.id,
            service_name="Full Service",
            quantity=Decimal("1"),
            unit_price=Decimal("200.00"),
            discount_percent=Decimal("0.00"),
            line_total=Decimal("200.00"),
        )
        db_session.add(applied)

        # Part (non-auto-deducted)
        part = PartUsed(
            service_order_item_id=oi.id,
            inventory_item_id=inv_item.id,
            quantity=Decimal("3"),
            unit_cost_at_use=Decimal("5.00"),
            unit_price_at_use=Decimal("15.00"),
            is_auto_deducted=False,
        )
        db_session.add(part)

        # Labor
        labor = LaborEntry(
            service_order_item_id=oi.id,
            tech_id=tech.id,
            hours=Decimal("1.50"),
            hourly_rate=Decimal("80.00"),
            work_date=date.today(),
        )
        db_session.add(labor)
        db_session.commit()

        invoice = invoice_service.generate_from_order(order.id)

        items = invoice.line_items.all()
        types = [i.line_type for i in items]
        assert "service" in types
        assert "part" in types
        assert "labor" in types
        assert len(items) == 3


# =========================================================================
# change_status (P1-1)
# =========================================================================


class TestChangeStatus:
    """Tests for change_status() transition validation."""

    def test_invoice_change_status_valid_transition(self, app, db_session):
        """draft -> sent succeeds."""
        invoice = _make_invoice(db_session, status="draft")

        result_invoice, success = invoice_service.change_status(invoice.id, "sent")

        assert success is True
        assert result_invoice is not None
        assert result_invoice.status == "sent"

    def test_invoice_change_status_invalid_transition(self, app, db_session):
        """draft -> paid fails (not in allowed transitions)."""
        invoice = _make_invoice(db_session, status="draft")

        result_invoice, success = invoice_service.change_status(invoice.id, "paid")

        assert success is False
        assert result_invoice is not None
        assert result_invoice.status == "draft"  # unchanged

    def test_invoice_change_status_void_is_terminal(self, app, db_session):
        """void -> anything fails (void is terminal)."""
        invoice = _make_invoice(db_session, status="void")

        for target in ["draft", "sent", "paid", "refunded"]:
            result_invoice, success = invoice_service.change_status(invoice.id, target)
            assert success is False
            assert result_invoice.status == "void"

    def test_invoice_change_status_paid_to_refunded(self, app, db_session):
        """paid -> refunded succeeds."""
        invoice = _make_invoice(db_session, status="paid")

        result_invoice, success = invoice_service.change_status(invoice.id, "refunded")

        assert success is True
        assert result_invoice.status == "refunded"

    def test_invoice_change_status_sets_paid_date(self, app, db_session):
        """Transitioning to 'paid' sets paid_date to today."""
        invoice = _make_invoice(db_session, status="sent")

        result_invoice, success = invoice_service.change_status(invoice.id, "paid")

        assert success is True
        assert result_invoice.paid_date == date.today()

    def test_invoice_change_status_not_found(self, app, db_session):
        """change_status() returns (None, False) for a non-existent ID."""
        result_invoice, success = invoice_service.change_status(99999, "sent")

        assert result_invoice is None
        assert success is False

    def test_invoice_change_status_empty_status(self, app, db_session):
        """change_status() with empty new_status returns (invoice, False)."""
        invoice = _make_invoice(db_session, status="draft")

        result_invoice, success = invoice_service.change_status(invoice.id, "")

        assert success is False
        assert result_invoice is not None

    def test_update_invoice_does_not_change_status(self, app, db_session):
        """status in data dict is ignored by update_invoice()."""
        invoice = _make_invoice(db_session, status="draft")

        updated = invoice_service.update_invoice(
            invoice.id,
            {"status": "paid", "notes": "Updated"},
        )

        assert updated is not None
        assert updated.notes == "Updated"
        assert updated.status == "draft"  # status unchanged


# =========================================================================
# Line Item negative price validation (P1-6)
# =========================================================================


class TestLineItemNegativePrice:
    """Tests for negative unit_price validation in add_line_item."""

    def test_add_line_item_negative_price_non_discount_fails(self, app, db_session):
        """ValueError raised when unit_price < 0 for non-discount type."""
        invoice = _make_invoice(db_session)

        data = {
            "line_type": "service",
            "description": "Negative service",
            "quantity": Decimal("1.00"),
            "unit_price": Decimal("-50.00"),
        }
        with pytest.raises(ValueError, match="non-negative"):
            invoice_service.add_line_item(invoice.id, data)

    def test_add_line_item_negative_price_discount_allowed(self, app, db_session):
        """Discount line items may have negative unit_price."""
        invoice = _make_invoice(db_session)

        data = {
            "line_type": "discount",
            "description": "Coupon discount",
            "quantity": Decimal("1.00"),
            "unit_price": Decimal("-25.00"),
        }
        item = invoice_service.add_line_item(invoice.id, data)

        assert item is not None
        assert item.unit_price == Decimal("-25.00")
        assert item.line_total == Decimal("-25.00")
