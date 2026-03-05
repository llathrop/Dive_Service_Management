"""Unit tests for the report service layer.

Tests cover revenue, orders, inventory, customer, and aging reports,
verifying that each returns the correct structure and values for both
empty and populated data sets.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.parts_used import PartUsed
from app.models.service_item import ServiceItem
from app.models.service_order import ServiceOrder
from app.models.service_order_item import ServiceOrderItem
from app.services import report_service
from tests.factories import (
    CustomerFactory,
    InventoryItemFactory,
    InvoiceFactory,
    InvoiceLineItemFactory,
    ServiceOrderFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    CustomerFactory._meta.sqlalchemy_session = db_session
    InventoryItemFactory._meta.sqlalchemy_session = db_session
    InvoiceFactory._meta.sqlalchemy_session = db_session
    InvoiceLineItemFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session


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


def _make_inventory_item(db_session, **kwargs):
    """Create and persist an InventoryItem with sensible defaults."""
    defaults = {
        "sku": kwargs.pop("sku", "SKU-RPT-001"),
        "name": "Test Part",
        "category": "Seals",
        "purchase_cost": Decimal("5.00"),
        "resale_price": Decimal("15.00"),
        "quantity_in_stock": 20,
        "reorder_level": 5,
        "unit_of_measure": "each",
        "is_active": True,
    }
    defaults.update(kwargs)
    item = InventoryItem(**defaults)
    db_session.add(item)
    db_session.commit()
    return item


def _make_order(db_session, customer=None, **kwargs):
    """Create and persist a ServiceOrder with sensible defaults."""
    if customer is None:
        customer = _make_customer(db_session)
    defaults = {
        "order_number": kwargs.pop("order_number", "SO-2026-00001"),
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


# =========================================================================
# Revenue Report
# =========================================================================


class TestRevenueReport:
    """Tests for revenue_report()."""

    def test_revenue_report_empty(self, app, db_session):
        """Returns zero totals when no invoices exist."""
        result = report_service.revenue_report()

        assert result["total_revenue"] == Decimal("0")
        assert result["parts_revenue"] == Decimal("0.00")
        assert result["labor_revenue"] == Decimal("0.00")
        assert result["services_revenue"] == Decimal("0.00")
        assert result["fees_revenue"] == Decimal("0.00")
        assert result["monthly_breakdown"] == []

    def test_revenue_report_with_data(self, app, db_session):
        """Returns correct totals for paid invoices with line items."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Rev", last_name="Test")
        invoice = InvoiceFactory(
            customer=customer,
            status="paid",
            issue_date=date(2026, 3, 1),
            subtotal=Decimal("300.00"),
            total=Decimal("300.00"),
            balance_due=Decimal("0.00"),
        )
        InvoiceLineItemFactory(
            invoice=invoice,
            line_type="service",
            quantity=Decimal("1.00"),
            unit_price=Decimal("150.00"),
            line_total=Decimal("150.00"),
        )
        InvoiceLineItemFactory(
            invoice=invoice,
            line_type="part",
            quantity=Decimal("2.00"),
            unit_price=Decimal("50.00"),
            line_total=Decimal("100.00"),
        )
        InvoiceLineItemFactory(
            invoice=invoice,
            line_type="labor",
            quantity=Decimal("1.00"),
            unit_price=Decimal("50.00"),
            line_total=Decimal("50.00"),
        )
        db_session.flush()

        result = report_service.revenue_report()

        assert result["total_revenue"] == Decimal("300.00")
        assert result["services_revenue"] == Decimal("150.00")
        assert result["parts_revenue"] == Decimal("100.00")
        assert result["labor_revenue"] == Decimal("50.00")
        assert len(result["monthly_breakdown"]) >= 1


# =========================================================================
# Orders Report
# =========================================================================


class TestOrdersReport:
    """Tests for orders_report()."""

    def test_orders_report_empty(self, app, db_session):
        """Returns zero totals when no orders exist."""
        result = report_service.orders_report()

        assert result["total_orders"] == 0
        assert result["status_breakdown"] == {}
        assert result["priority_breakdown"] == {}
        assert result["avg_turnaround_days"] is None
        assert result["orders_by_tech"] == []

    def test_orders_report_with_data(self, app, db_session):
        """Returns correct counts for orders with different statuses."""
        customer = _make_customer(db_session)
        _make_order(
            db_session, customer=customer,
            order_number="SO-2026-10001", status="intake", priority="normal",
        )
        _make_order(
            db_session, customer=customer,
            order_number="SO-2026-10002", status="intake", priority="rush",
        )
        _make_order(
            db_session, customer=customer,
            order_number="SO-2026-10003", status="in_progress", priority="normal",
        )

        result = report_service.orders_report()

        assert result["total_orders"] == 3
        assert result["status_breakdown"]["intake"] == 2
        assert result["status_breakdown"]["in_progress"] == 1
        assert result["priority_breakdown"]["normal"] == 2
        assert result["priority_breakdown"]["rush"] == 1


# =========================================================================
# Inventory Report
# =========================================================================


class TestInventoryReport:
    """Tests for inventory_report()."""

    def test_inventory_report_empty(self, app, db_session):
        """Returns zero totals when no inventory exists."""
        result = report_service.inventory_report()

        assert result["total_items"] == 0
        assert result["total_value"] == Decimal("0")
        assert result["low_stock_items"] == []
        assert result["out_of_stock_count"] == 0
        assert result["category_breakdown"] == {}
        assert result["most_used_parts"] == []

    def test_inventory_report_with_data(self, app, db_session):
        """Returns correct inventory counts and low stock items."""
        item1 = _make_inventory_item(
            db_session, sku="SKU-INV-01", name="O-Ring",
            category="Seals", quantity_in_stock=20,
            purchase_cost=Decimal("2.00"), reorder_level=5,
        )
        item2 = _make_inventory_item(
            db_session, sku="SKU-INV-02", name="Neck Seal",
            category="Seals", quantity_in_stock=3,
            purchase_cost=Decimal("10.00"), reorder_level=5,
        )
        item3 = _make_inventory_item(
            db_session, sku="SKU-INV-03", name="Zipper",
            category="Zippers", quantity_in_stock=0,
            purchase_cost=Decimal("50.00"), reorder_level=2,
        )

        result = report_service.inventory_report()

        assert result["total_items"] == 3
        # total_value = 20*2 + 3*10 + 0*50 = 40 + 30 + 0 = 70
        assert result["total_value"] == Decimal("70")
        # Low stock: item2 (3 <= 5) and item3 (0 <= 2)
        low_stock_ids = [i.id for i in result["low_stock_items"]]
        assert item2.id in low_stock_ids
        assert item3.id in low_stock_ids
        assert item1.id not in low_stock_ids
        # Out of stock: item3
        assert result["out_of_stock_count"] == 1
        # Category breakdown
        assert result["category_breakdown"]["Seals"] == 2
        assert result["category_breakdown"]["Zippers"] == 1


# =========================================================================
# Customer Report
# =========================================================================


class TestCustomerReport:
    """Tests for customer_report()."""

    def test_customer_report_empty(self, app, db_session):
        """Returns zero totals when no customers exist."""
        result = report_service.customer_report()

        assert result["total_customers"] == 0
        assert result["new_customers"] == 0
        assert result["top_customers"] == []

    def test_customer_report_with_data(self, app, db_session):
        """Returns correct customer counts."""
        _set_session(db_session)
        CustomerFactory(first_name="Alice", last_name="Diver")
        CustomerFactory(first_name="Bob", last_name="Swimmer")

        result = report_service.customer_report()

        assert result["total_customers"] == 2
        assert result["new_customers"] == 2


# =========================================================================
# Aging Report
# =========================================================================


class TestAgingReport:
    """Tests for aging_report()."""

    def test_aging_report_empty(self, app, db_session):
        """Returns empty buckets when no invoices exist."""
        result = report_service.aging_report()

        assert "buckets" in result
        assert len(result["buckets"]) == 5
        for bucket in result["buckets"]:
            assert bucket["count"] == 0
            assert bucket["total_amount"] == Decimal("0.00")

    def test_aging_report_with_data(self, app, db_session):
        """Returns correct bucket assignments for invoices with different due dates."""
        _set_session(db_session)
        today = date.today()
        customer = CustomerFactory(first_name="Aging", last_name="Test")

        # Current invoice (due in the future)
        InvoiceFactory(
            customer=customer,
            status="sent",
            issue_date=today,
            due_date=today + timedelta(days=15),
            balance_due=Decimal("100.00"),
        )
        # 1-30 days overdue
        InvoiceFactory(
            customer=customer,
            status="sent",
            issue_date=today - timedelta(days=45),
            due_date=today - timedelta(days=15),
            balance_due=Decimal("200.00"),
        )
        # 31-60 days overdue
        InvoiceFactory(
            customer=customer,
            status="sent",
            issue_date=today - timedelta(days=90),
            due_date=today - timedelta(days=45),
            balance_due=Decimal("300.00"),
        )
        # 90+ days overdue
        InvoiceFactory(
            customer=customer,
            status="sent",
            issue_date=today - timedelta(days=180),
            due_date=today - timedelta(days=120),
            balance_due=Decimal("500.00"),
        )

        result = report_service.aging_report()
        buckets = result["buckets"]

        # Current bucket
        assert buckets[0]["count"] == 1
        assert buckets[0]["total_amount"] == Decimal("100.00")
        # 1-30 days bucket
        assert buckets[1]["count"] == 1
        assert buckets[1]["total_amount"] == Decimal("200.00")
        # 31-60 days bucket
        assert buckets[2]["count"] == 1
        assert buckets[2]["total_amount"] == Decimal("300.00")
        # 90+ days bucket
        assert buckets[4]["count"] == 1
        assert buckets[4]["total_amount"] == Decimal("500.00")
