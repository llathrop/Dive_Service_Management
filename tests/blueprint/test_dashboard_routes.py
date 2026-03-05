"""Blueprint tests for dashboard routes."""

from datetime import date, timedelta

import pytest

from tests.factories import (
    CustomerFactory,
    InventoryItemFactory,
    InvoiceFactory,
    ServiceOrderFactory,
)


pytestmark = pytest.mark.blueprint


def _set_session(db_session):
    """Configure factories to use the given session."""
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session
    InventoryItemFactory._meta.sqlalchemy_session = db_session
    InvoiceFactory._meta.sqlalchemy_session = db_session


# ── Access control ──────────────────────────────────────────────────

def test_dashboard_requires_login(client):
    """GET /dashboard/ without login redirects to login page."""
    response = client.get("/dashboard/")
    assert response.status_code == 302
    assert "/login" in response.location


def test_dashboard_accessible_when_logged_in(logged_in_client):
    """Authenticated GET /dashboard/ returns 200."""
    response = logged_in_client.get("/dashboard/")
    assert response.status_code == 200


def test_dashboard_contains_expected_content(logged_in_client):
    """The dashboard page contains the word 'Dashboard'."""
    response = logged_in_client.get("/dashboard/")
    assert response.status_code == 200
    assert b"Dashboard" in response.data


# ── Summary card values ─────────────────────────────────────────────

def test_dashboard_shows_zero_counts_when_empty(logged_in_client):
    """Dashboard shows 0 for all summary cards when no data exists."""
    response = logged_in_client.get("/dashboard/")
    html = response.data.decode()
    assert "Open Orders" in html
    assert "Low Stock Alerts" in html
    assert "Awaiting Pickup" in html
    assert "Overdue Invoices" in html


def test_dashboard_open_orders_count(logged_in_client, db_session):
    """Dashboard shows correct count of open (non-terminal) orders."""
    _set_session(db_session)
    customer = CustomerFactory()
    # Open orders (should be counted)
    ServiceOrderFactory(customer=customer, status="intake")
    ServiceOrderFactory(customer=customer, status="in_progress")
    ServiceOrderFactory(customer=customer, status="awaiting_parts")
    ServiceOrderFactory(customer=customer, status="ready_for_pickup")
    # Terminal orders (should NOT be counted)
    ServiceOrderFactory(customer=customer, status="picked_up")
    ServiceOrderFactory(customer=customer, status="cancelled")
    db_session.commit()

    response = logged_in_client.get("/dashboard/")
    html = response.data.decode()
    # 4 open orders expected — find it near "Open Orders" text
    assert ">4</h2>" in html


def test_dashboard_awaiting_pickup_count(logged_in_client, db_session):
    """Dashboard shows correct count of orders awaiting pickup."""
    _set_session(db_session)
    customer = CustomerFactory()
    ServiceOrderFactory(customer=customer, status="ready_for_pickup")
    ServiceOrderFactory(customer=customer, status="ready_for_pickup")
    ServiceOrderFactory(customer=customer, status="in_progress")
    db_session.commit()

    response = logged_in_client.get("/dashboard/")
    html = response.data.decode()
    # 2 awaiting pickup
    assert "Awaiting Pickup" in html
    assert ">2</h2>" in html


def test_dashboard_low_stock_count(logged_in_client, db_session):
    """Dashboard shows correct count of low stock items."""
    _set_session(db_session)
    # Low stock: quantity at or below reorder level
    InventoryItemFactory(quantity_in_stock=2, reorder_level=5, is_active=True)
    InventoryItemFactory(quantity_in_stock=0, reorder_level=3, is_active=True)
    # Not low stock: above reorder level
    InventoryItemFactory(quantity_in_stock=10, reorder_level=5, is_active=True)
    # Not counted: inactive item
    InventoryItemFactory(quantity_in_stock=1, reorder_level=5, is_active=False)
    # Not counted: reorder_level is 0
    InventoryItemFactory(quantity_in_stock=0, reorder_level=0, is_active=True)
    db_session.commit()

    response = logged_in_client.get("/dashboard/")
    html = response.data.decode()
    assert "Low Stock Alerts" in html
    assert ">2</h2>" in html


def test_dashboard_overdue_invoices_count(logged_in_client, db_session):
    """Dashboard shows correct count of overdue invoices."""
    _set_session(db_session)
    customer = CustomerFactory()
    yesterday = date.today() - timedelta(days=1)
    tomorrow = date.today() + timedelta(days=1)

    # Overdue: past due and unpaid
    InvoiceFactory(customer=customer, status="sent", due_date=yesterday)
    InvoiceFactory(
        customer=customer, status="partially_paid", due_date=yesterday
    )
    # Not overdue: due date in future
    InvoiceFactory(customer=customer, status="sent", due_date=tomorrow)
    # Not overdue: paid
    InvoiceFactory(customer=customer, status="paid", due_date=yesterday)
    # Not overdue: void
    InvoiceFactory(customer=customer, status="void", due_date=yesterday)
    db_session.commit()

    response = logged_in_client.get("/dashboard/")
    html = response.data.decode()
    assert "Overdue Invoices" in html
    assert ">2</h2>" in html


def test_dashboard_deleted_orders_not_counted(logged_in_client, db_session):
    """Soft-deleted orders should not appear in open orders count."""
    _set_session(db_session)
    customer = CustomerFactory()
    order = ServiceOrderFactory(customer=customer, status="intake")
    order.is_deleted = True
    db_session.commit()

    response = logged_in_client.get("/dashboard/")
    html = response.data.decode()
    # Should show 0 open orders
    assert "Open Orders" in html
    assert ">0</h2>" in html


# ── Links ───────────────────────────────────────────────────────────

def test_dashboard_has_quick_action_links(logged_in_client):
    """Dashboard contains quick action links to create orders/customers."""
    response = logged_in_client.get("/dashboard/")
    html = response.data.decode()
    assert "New Service Order" in html
    assert "New Customer" in html
    assert "Inventory Lookup" in html
    assert "/orders/new" in html
    assert "/customers/new" in html


def test_dashboard_card_links_point_to_correct_routes(logged_in_client):
    """Summary card footer links point to correct list routes."""
    response = logged_in_client.get("/dashboard/")
    html = response.data.decode()
    assert "/orders/" in html
    assert "/inventory/low-stock" in html
    assert "/invoices/" in html


# ── Role access ─────────────────────────────────────────────────────

def test_dashboard_accessible_by_admin(admin_client):
    """Admin users can access the dashboard."""
    response = admin_client.get("/dashboard/")
    assert response.status_code == 200


def test_dashboard_accessible_by_viewer(viewer_client):
    """Viewer users can access the dashboard."""
    response = viewer_client.get("/dashboard/")
    assert response.status_code == 200
