"""Unit tests for the ServiceOrderItem model.

Tests cover creation, defaults, relationships to order, service item,
notes, parts used, labor entries, and applied services.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.service_order_item import (
    VALID_STATUSES,
    VALID_WARRANTY_TYPES,
    ServiceOrderItem,
)
from tests.factories import (
    AppliedServiceFactory,
    CustomerFactory,
    InventoryItemFactory,
    LaborEntryFactory,
    PartUsedFactory,
    ServiceItemFactory,
    ServiceNoteFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
    UserFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    ServiceOrderFactory._meta.sqlalchemy_session = db_session
    ServiceOrderItemFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session
    ServiceNoteFactory._meta.sqlalchemy_session = db_session
    PartUsedFactory._meta.sqlalchemy_session = db_session
    LaborEntryFactory._meta.sqlalchemy_session = db_session
    AppliedServiceFactory._meta.sqlalchemy_session = db_session
    InventoryItemFactory._meta.sqlalchemy_session = db_session
    UserFactory._meta.sqlalchemy_session = db_session


class TestServiceOrderItemCreation:
    """Tests for basic order item creation and persistence."""

    def test_create_order_item(self, app, db_session):
        """An order item persists with required fields."""
        _set_session(db_session)
        order = ServiceOrderFactory()
        service_item = ServiceItemFactory(name="Regulator Set")
        item = ServiceOrderItemFactory(
            order=order,
            service_item=service_item,
            work_description="Full service",
        )

        fetched = db_session.get(ServiceOrderItem, item.id)
        assert fetched is not None
        assert fetched.order_id == order.id
        assert fetched.service_item_id == service_item.id
        assert fetched.work_description == "Full service"

    def test_defaults(self, app, db_session):
        """Default values are applied correctly."""
        _set_session(db_session)
        order = ServiceOrderFactory()
        service_item = ServiceItemFactory()
        item = ServiceOrderItem(
            order_id=order.id,
            service_item_id=service_item.id,
        )
        db_session.add(item)
        db_session.commit()

        fetched = db_session.get(ServiceOrderItem, item.id)
        assert fetched.status == "pending"
        assert fetched.warranty_type == "none"
        assert fetched.customer_approved is False


class TestServiceOrderItemConstants:
    """Tests for validation constants."""

    def test_valid_statuses(self, app):
        """VALID_STATUSES contains expected item statuses."""
        expected = ["pending", "in_progress", "completed", "cancelled", "returned_unserviceable"]
        assert VALID_STATUSES == expected

    def test_valid_warranty_types(self, app):
        """VALID_WARRANTY_TYPES contains expected warranty types."""
        expected = ["none", "standard", "extended", "manufacturer"]
        assert VALID_WARRANTY_TYPES == expected


class TestServiceOrderItemRelationships:
    """Tests for model relationships."""

    def test_order_relationship(self, app, db_session):
        """An order item links to its parent order."""
        _set_session(db_session)
        order = ServiceOrderFactory(order_number="SO-2026-00010")
        item = ServiceOrderItemFactory(order=order)

        assert item.order.id == order.id
        assert item.order.order_number == "SO-2026-00010"

    def test_service_item_relationship(self, app, db_session):
        """An order item links to its service item."""
        _set_session(db_session)
        si = ServiceItemFactory(name="BCD Vest")
        item = ServiceOrderItemFactory(service_item=si)

        assert item.service_item.id == si.id
        assert item.service_item.name == "BCD Vest"

    def test_notes_relationship(self, app, db_session):
        """An order item can have multiple notes."""
        _set_session(db_session)
        user = UserFactory()
        item = ServiceOrderItemFactory()
        note1 = ServiceNoteFactory(order_item=item, note_text="First note", created_by=user.id)
        note2 = ServiceNoteFactory(order_item=item, note_text="Second note", created_by=user.id)

        notes = item.notes.all()
        assert len(notes) == 2
        texts = {n.note_text for n in notes}
        assert "First note" in texts
        assert "Second note" in texts

    def test_parts_used_relationship(self, app, db_session):
        """An order item can have multiple parts used."""
        _set_session(db_session)
        item = ServiceOrderItemFactory()
        part1 = PartUsedFactory(order_item=item)
        part2 = PartUsedFactory(order_item=item)

        parts = item.parts_used.all()
        assert len(parts) == 2
        part_ids = {p.id for p in parts}
        assert part1.id in part_ids
        assert part2.id in part_ids

    def test_labor_entries_relationship(self, app, db_session):
        """An order item can have multiple labor entries."""
        _set_session(db_session)
        tech = UserFactory()
        item = ServiceOrderItemFactory()
        labor1 = LaborEntryFactory(order_item=item, tech=tech)
        labor2 = LaborEntryFactory(order_item=item, tech=tech)

        entries = item.labor_entries.all()
        assert len(entries) == 2
        entry_ids = {e.id for e in entries}
        assert labor1.id in entry_ids
        assert labor2.id in entry_ids

    def test_applied_services_relationship(self, app, db_session):
        """An order item can have multiple applied services."""
        _set_session(db_session)
        item = ServiceOrderItemFactory()
        svc1 = AppliedServiceFactory(order_item=item, service_name="Seal Replacement")
        svc2 = AppliedServiceFactory(order_item=item, service_name="Pressure Test")

        services = item.applied_services.all()
        assert len(services) == 2
        names = {s.service_name for s in services}
        assert "Seal Replacement" in names
        assert "Pressure Test" in names


class TestServiceOrderItemRepr:
    """Tests for __repr__."""

    def test_repr(self, app, db_session):
        """__repr__ includes id, order_id, and service_item_id."""
        _set_session(db_session)
        item = ServiceOrderItemFactory()
        expected = (
            f"<ServiceOrderItem {item.id} order={item.order_id} "
            f"item={item.service_item_id}>"
        )
        assert repr(item) == expected
