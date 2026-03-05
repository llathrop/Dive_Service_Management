"""Unit tests for the order service layer.

Tests cover paginated listing, search, filtering, CRUD operations,
soft-delete, order number generation, status transitions, order items,
parts used, labor entries, service notes, and order summary calculations.
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
from app.models.user import User
from app.services import order_service

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


def _make_service_item(db_session, **kwargs):
    """Create and persist a ServiceItem with sensible defaults."""
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


def _make_inventory_item(db_session, **kwargs):
    """Create and persist an InventoryItem with sensible defaults."""
    defaults = {
        "sku": kwargs.pop("sku", "SKU-99999"),
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


def _make_user(db_session, **kwargs):
    """Create and persist a User."""
    import uuid
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


# =========================================================================
# get_orders
# =========================================================================

class TestGetOrders:
    """Tests for get_orders()."""

    def test_get_orders_empty(self, app, db_session):
        """Returns empty pagination when no orders exist."""
        result = order_service.get_orders(page=1, per_page=25)
        assert result.total == 0
        assert len(result.items) == 0

    def test_get_orders_with_data(self, app, db_session):
        """Returns orders when they exist."""
        customer = _make_customer(db_session)
        _make_order(db_session, customer=customer, order_number="SO-2026-00001")
        _make_order(db_session, customer=customer, order_number="SO-2026-00002")

        result = order_service.get_orders(page=1, per_page=25)
        assert result.total == 2
        assert len(result.items) == 2

    def test_get_orders_excludes_deleted(self, app, db_session):
        """Soft-deleted orders are not returned."""
        customer = _make_customer(db_session)
        o1 = _make_order(db_session, customer=customer, order_number="SO-2026-00010")
        o2 = _make_order(db_session, customer=customer, order_number="SO-2026-00011")
        o2.soft_delete()
        db_session.commit()

        result = order_service.get_orders()
        ids = [o.id for o in result.items]
        assert o1.id in ids
        assert o2.id not in ids

    def test_get_orders_search(self, app, db_session):
        """Search by order_number returns matching results."""
        customer = _make_customer(db_session)
        _make_order(db_session, customer=customer, order_number="SO-2026-00100")
        _make_order(db_session, customer=customer, order_number="SO-2026-00200")

        result = order_service.get_orders(search="00100")
        assert result.total == 1
        assert result.items[0].order_number == "SO-2026-00100"

    def test_get_orders_filter_status(self, app, db_session):
        """Filtering by status returns only matching orders."""
        customer = _make_customer(db_session)
        _make_order(db_session, customer=customer, order_number="SO-2026-00300", status="intake")
        _make_order(db_session, customer=customer, order_number="SO-2026-00301", status="in_progress")

        result = order_service.get_orders(status="in_progress")
        assert result.total == 1
        assert result.items[0].status == "in_progress"

    def test_get_orders_filter_priority(self, app, db_session):
        """Filtering by priority returns only matching orders."""
        customer = _make_customer(db_session)
        _make_order(db_session, customer=customer, order_number="SO-2026-00400", priority="rush")
        _make_order(db_session, customer=customer, order_number="SO-2026-00401", priority="normal")

        result = order_service.get_orders(priority="rush")
        assert result.total == 1
        assert result.items[0].priority == "rush"


# =========================================================================
# get_order
# =========================================================================

class TestGetOrder:
    """Tests for get_order()."""

    def test_get_order_found(self, app, db_session):
        """get_order() returns the correct order by ID."""
        order = _make_order(db_session)
        result = order_service.get_order(order.id)
        assert result.id == order.id

    def test_get_order_not_found(self, app, db_session):
        """get_order() raises 404 for a non-existent ID."""
        with pytest.raises(Exception) as exc_info:
            order_service.get_order(99999)
        assert exc_info.value.code == 404

    def test_get_order_deleted(self, app, db_session):
        """get_order() raises 404 for a soft-deleted order."""
        order = _make_order(db_session)
        order.soft_delete()
        db_session.commit()

        with pytest.raises(Exception) as exc_info:
            order_service.get_order(order.id)
        assert exc_info.value.code == 404


# =========================================================================
# create_order
# =========================================================================

class TestCreateOrder:
    """Tests for create_order()."""

    def test_create_order(self, app, db_session):
        """create_order() persists an order with auto-generated order_number."""
        customer = _make_customer(db_session)
        data = {
            "customer_id": customer.id,
            "priority": "high",
            "date_received": date.today(),
            "description": "Rush job",
        }
        order = order_service.create_order(data)

        assert order.id is not None
        assert order.customer_id == customer.id
        assert order.priority == "high"
        assert order.description == "Rush job"

        # Verify persistence
        fetched = db_session.get(ServiceOrder, order.id)
        assert fetched is not None

    def test_create_order_generates_number(self, app, db_session):
        """create_order() generates an order_number in SO-YYYY-NNNNN format."""
        customer = _make_customer(db_session)
        data = {"customer_id": customer.id, "date_received": date.today()}
        order = order_service.create_order(data)

        import re
        pattern = r"^SO-\d{4}-\d{5}$"
        assert re.match(pattern, order.order_number), (
            f"Order number {order.order_number!r} does not match pattern"
        )


# =========================================================================
# update_order
# =========================================================================

class TestUpdateOrder:
    """Tests for update_order()."""

    def test_update_order(self, app, db_session):
        """update_order() updates specified fields."""
        order = _make_order(db_session)

        updated = order_service.update_order(
            order.id,
            {"priority": "rush", "description": "Updated description"},
        )

        assert updated.priority == "rush"
        assert updated.description == "Updated description"
        # Unchanged fields
        assert updated.status == "intake"


# =========================================================================
# delete_order
# =========================================================================

class TestDeleteOrder:
    """Tests for delete_order()."""

    def test_delete_order(self, app, db_session):
        """delete_order() soft-deletes the order."""
        order = _make_order(db_session)

        result = order_service.delete_order(order.id)

        assert result.is_deleted is True
        assert result.deleted_at is not None

        # Verify it's excluded from not_deleted queries
        active = ServiceOrder.not_deleted().all()
        assert order.id not in [o.id for o in active]


# =========================================================================
# change_status
# =========================================================================

class TestChangeStatus:
    """Tests for change_status()."""

    def test_change_status_valid(self, app, db_session):
        """A valid transition updates the status and returns success."""
        order = _make_order(db_session, status="intake")

        result_order, success = order_service.change_status(order.id, "assessment")

        assert success is True
        assert result_order.status == "assessment"

    def test_change_status_invalid(self, app, db_session):
        """An invalid transition does not change status and returns False."""
        order = _make_order(db_session, status="intake")

        result_order, success = order_service.change_status(order.id, "completed")

        assert success is False
        assert result_order.status == "intake"

    def test_change_status_sets_completed_date(self, app, db_session):
        """Transitioning to 'completed' sets date_completed."""
        order = _make_order(db_session, status="in_progress")

        result_order, success = order_service.change_status(order.id, "completed")

        assert success is True
        assert result_order.date_completed == date.today()

    def test_change_status_sets_pickup_date(self, app, db_session):
        """Transitioning to 'picked_up' sets date_picked_up."""
        order = _make_order(db_session, status="ready_for_pickup")

        result_order, success = order_service.change_status(order.id, "picked_up")

        assert success is True
        assert result_order.date_picked_up == date.today()

    def test_change_status_assessment_to_in_progress(self, app, db_session):
        """Assessment can transition to in_progress."""
        order = _make_order(db_session, status="assessment")

        result_order, success = order_service.change_status(order.id, "in_progress")

        assert success is True
        assert result_order.status == "in_progress"

    def test_change_status_cancelled_to_intake(self, app, db_session):
        """A cancelled order can be reopened back to intake."""
        order = _make_order(db_session, status="cancelled")

        result_order, success = order_service.change_status(order.id, "intake")

        assert success is True
        assert result_order.status == "intake"


# =========================================================================
# Order Items
# =========================================================================

class TestOrderItems:
    """Tests for add_order_item and remove_order_item."""

    def test_add_order_item(self, app, db_session):
        """add_order_item() creates a ServiceOrderItem."""
        order = _make_order(db_session)
        si = _make_service_item(db_session)

        oi = order_service.add_order_item(order.id, si.id, work_description="Full service")

        assert oi.id is not None
        assert oi.order_id == order.id
        assert oi.service_item_id == si.id
        assert oi.work_description == "Full service"

    def test_add_order_item_duplicate(self, app, db_session):
        """Adding the same service item to an order twice raises ValueError."""
        order = _make_order(db_session)
        si = _make_service_item(db_session)

        order_service.add_order_item(order.id, si.id)

        with pytest.raises(ValueError, match="already on order"):
            order_service.add_order_item(order.id, si.id)

    def test_remove_order_item(self, app, db_session):
        """remove_order_item() deletes the item and returns True."""
        order = _make_order(db_session)
        si = _make_service_item(db_session)
        oi = order_service.add_order_item(order.id, si.id)

        result = order_service.remove_order_item(oi.id)

        assert result is True
        assert db_session.get(ServiceOrderItem, oi.id) is None

    def test_remove_nonexistent_order_item(self, app, db_session):
        """remove_order_item() returns False for a non-existent ID."""
        result = order_service.remove_order_item(99999)
        assert result is False


# =========================================================================
# Parts Used
# =========================================================================

class TestPartsUsed:
    """Tests for add_part_used and remove_part_used."""

    def test_add_part_used(self, app, db_session):
        """add_part_used() creates a PartUsed and deducts inventory."""
        order = _make_order(db_session)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        inv = _make_inventory_item(db_session, quantity_in_stock=50)

        part = order_service.add_part_used(
            order_item_id=oi.id,
            inventory_item_id=inv.id,
            quantity=2,
        )

        assert part.id is not None
        assert part.service_order_item_id == oi.id
        assert part.inventory_item_id == inv.id
        assert part.quantity == 2

        # Inventory should be deducted
        db_session.refresh(inv)
        assert inv.quantity_in_stock == 48

    def test_remove_part_used(self, app, db_session):
        """remove_part_used() deletes the record and restores inventory."""
        order = _make_order(db_session)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        inv = _make_inventory_item(db_session, quantity_in_stock=50)

        part = order_service.add_part_used(
            order_item_id=oi.id,
            inventory_item_id=inv.id,
            quantity=5,
        )

        db_session.refresh(inv)
        assert inv.quantity_in_stock == 45

        result = order_service.remove_part_used(part.id)

        assert result is True
        assert db_session.get(PartUsed, part.id) is None
        db_session.refresh(inv)
        assert inv.quantity_in_stock == 50

    def test_remove_nonexistent_part(self, app, db_session):
        """remove_part_used() returns False for a non-existent ID."""
        result = order_service.remove_part_used(99999)
        assert result is False


# =========================================================================
# Labor Entries
# =========================================================================

class TestLaborEntries:
    """Tests for add_labor_entry and remove_labor_entry."""

    def test_add_labor_entry(self, app, db_session):
        """add_labor_entry() creates a LaborEntry."""
        order = _make_order(db_session)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        tech = _make_user(db_session)

        entry = order_service.add_labor_entry(
            order_item_id=oi.id,
            tech_id=tech.id,
            hours=Decimal("2.50"),
            hourly_rate=Decimal("75.00"),
            description="Regulator rebuild",
            work_date=date(2026, 3, 1),
        )

        assert entry.id is not None
        assert entry.service_order_item_id == oi.id
        assert entry.tech_id == tech.id
        assert entry.hours == Decimal("2.50")
        assert entry.hourly_rate == Decimal("75.00")
        assert entry.work_date == date(2026, 3, 1)

    def test_remove_labor_entry(self, app, db_session):
        """remove_labor_entry() deletes the entry and returns True."""
        order = _make_order(db_session)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        tech = _make_user(db_session)

        entry = order_service.add_labor_entry(
            order_item_id=oi.id,
            tech_id=tech.id,
            hours=Decimal("1.00"),
            hourly_rate=Decimal("75.00"),
        )

        result = order_service.remove_labor_entry(entry.id)

        assert result is True
        assert db_session.get(LaborEntry, entry.id) is None

    def test_remove_nonexistent_labor_entry(self, app, db_session):
        """remove_labor_entry() returns False for a non-existent ID."""
        result = order_service.remove_labor_entry(99999)
        assert result is False


# =========================================================================
# Service Notes
# =========================================================================

class TestServiceNotes:
    """Tests for add_service_note."""

    def test_add_service_note(self, app, db_session):
        """add_service_note() creates a ServiceNote."""
        order = _make_order(db_session)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        tech = _make_user(db_session)

        note = order_service.add_service_note(
            order_item_id=oi.id,
            note_text="Found damaged O-ring during inspection.",
            note_type="diagnostic",
            created_by=tech.id,
        )

        assert note.id is not None
        assert note.service_order_item_id == oi.id
        assert note.note_text == "Found damaged O-ring during inspection."
        assert note.note_type == "diagnostic"
        assert note.created_by == tech.id

    def test_add_service_note_defaults(self, app, db_session):
        """add_service_note() uses 'general' note_type by default."""
        order = _make_order(db_session)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        tech = _make_user(db_session)

        note = order_service.add_service_note(
            order_item_id=oi.id,
            note_text="General observation.",
            created_by=tech.id,
        )

        assert note.note_type == "general"


# =========================================================================
# Order Summary
# =========================================================================

class TestGetOrderSummary:
    """Tests for get_order_summary()."""

    def test_get_order_summary_empty(self, app, db_session):
        """Summary of an order with no items returns all zeros."""
        order = _make_order(db_session)
        summary = order_service.get_order_summary(order.id)

        assert summary["applied_services_total"] == Decimal("0.00")
        assert summary["parts_total"] == Decimal("0.00")
        assert summary["labor_total"] == Decimal("0.00")
        assert summary["estimated_total"] == Decimal("0.00")

    def test_get_order_summary_with_data(self, app, db_session):
        """Summary aggregates applied services, parts, and labor."""
        customer = _make_customer(db_session)
        order = _make_order(db_session, customer=customer)
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)
        tech = _make_user(db_session)

        # Add an applied service
        applied = AppliedService(
            service_order_item_id=oi.id,
            service_name="Standard Service",
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            discount_percent=Decimal("0.00"),
            line_total=Decimal("100.00"),
        )
        db_session.add(applied)

        # Add a manually added part (not auto-deducted)
        inv = _make_inventory_item(db_session, sku="SKU-SUM-01")
        part = PartUsed(
            service_order_item_id=oi.id,
            inventory_item_id=inv.id,
            quantity=Decimal("2"),
            unit_cost_at_use=Decimal("5.00"),
            unit_price_at_use=Decimal("10.00"),
            is_auto_deducted=False,
        )
        db_session.add(part)

        # Add labor
        labor = LaborEntry(
            service_order_item_id=oi.id,
            tech_id=tech.id,
            hours=Decimal("2.00"),
            hourly_rate=Decimal("75.00"),
            work_date=date.today(),
        )
        db_session.add(labor)
        db_session.commit()

        summary = order_service.get_order_summary(order.id)

        assert summary["applied_services_total"] == Decimal("100.00")
        assert summary["parts_total"] == Decimal("20.00")  # 2 * 10
        assert summary["labor_total"] == Decimal("150.00")  # 2 * 75
        assert summary["subtotal"] == Decimal("270.00")
        assert summary["estimated_total"] == Decimal("270.00")

    def test_get_order_summary_with_discounts(self, app, db_session):
        """Summary applies order-level discount percent and amount."""
        customer = _make_customer(db_session)
        order = _make_order(
            db_session,
            customer=customer,
            discount_percent=Decimal("10.00"),
            discount_amount=Decimal("5.00"),
        )
        si = _make_service_item(db_session)
        oi = _make_order_item(db_session, order=order, service_item=si)

        applied = AppliedService(
            service_order_item_id=oi.id,
            service_name="Service A",
            quantity=Decimal("1"),
            unit_price=Decimal("200.00"),
            discount_percent=Decimal("0.00"),
            line_total=Decimal("200.00"),
        )
        db_session.add(applied)
        db_session.commit()

        summary = order_service.get_order_summary(order.id)

        assert summary["subtotal"] == Decimal("200.00")
        # 10% of 200 = 20.00 + 5.00 flat = 25.00 total discount
        assert summary["discount_total"] == Decimal("25.00")
        assert summary["estimated_total"] == Decimal("175.00")
