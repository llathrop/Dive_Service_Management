"""Unit tests for the ServiceItem model.

Tests cover creation, serial number uniqueness, relationships,
properties, soft-delete, and JSON custom fields.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.service_item import ServiceItem
from tests.factories import (
    CustomerFactory,
    DrysuitDetailsFactory,
    ServiceItemFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    ServiceItemFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    DrysuitDetailsFactory._meta.sqlalchemy_session = db_session


class TestServiceItemCreation:
    """Tests for basic ServiceItem creation."""

    def test_create_service_item(self, app, db_session):
        """A service item persists with required fields."""
        _set_session(db_session)
        item = ServiceItemFactory(
            name="Apeks XTX50 Regulator",
            item_category="Regulator",
            brand="Apeks",
            model="XTX50",
        )

        fetched = db_session.get(ServiceItem, item.id)
        assert fetched is not None
        assert fetched.name == "Apeks XTX50 Regulator"
        assert fetched.item_category == "Regulator"
        assert fetched.brand == "Apeks"
        assert fetched.model == "XTX50"

    def test_service_item_with_serial(self, app, db_session):
        """A service item can have a unique serial number."""
        _set_session(db_session)
        item = ServiceItemFactory(
            name="Test Item",
            serial_number="SN-12345",
        )

        fetched = db_session.get(ServiceItem, item.id)
        assert fetched.serial_number == "SN-12345"


class TestServiceItemSerialUniqueness:
    """Tests for serial number uniqueness constraint."""

    def test_duplicate_serial_raises(self, app, db_session):
        """Inserting a duplicate serial_number raises IntegrityError."""
        _set_session(db_session)
        ServiceItemFactory(name="Item A", serial_number="DUP-001")

        with pytest.raises(IntegrityError):
            ServiceItemFactory(name="Item B", serial_number="DUP-001")
            db_session.flush()


class TestServiceItemRelationships:
    """Tests for ServiceItem relationships."""

    def test_service_item_customer_relationship(self, app, db_session):
        """FK navigation between ServiceItem and Customer works."""
        _set_session(db_session)
        customer = CustomerFactory(
            first_name="Test",
            last_name="Owner",
        )
        item = ServiceItemFactory(
            name="Owner's Regulator",
            customer=customer,
        )

        fetched = db_session.get(ServiceItem, item.id)
        assert fetched.customer is not None
        assert fetched.customer.id == customer.id
        assert fetched.customer_id == customer.id

    def test_service_item_drysuit_details(self, app, db_session):
        """The one-to-one DrysuitDetails relationship works correctly."""
        _set_session(db_session)
        details = DrysuitDetailsFactory(
            size="L",
            material_type="Trilaminate",
            neck_seal_type="Silicone",
        )

        item = details.service_item
        assert item is not None
        assert item.item_category == "Drysuit"
        assert item.is_drysuit is True
        assert item.drysuit_details is not None
        assert item.drysuit_details.size == "L"
        assert item.drysuit_details.material_type == "Trilaminate"
        assert item.drysuit_details.neck_seal_type == "Silicone"


class TestServiceItemDefaults:
    """Tests for default values."""

    def test_service_item_serviceability_default(self, app, db_session):
        """Serviceability defaults to 'serviceable'."""
        _set_session(db_session)
        item = ServiceItemFactory(name="Default Test")

        assert item.serviceability == "serviceable"


class TestServiceItemSoftDelete:
    """Tests for soft-delete support."""

    def test_service_item_soft_delete(self, app, db_session):
        """soft_delete() flags the item and not_deleted() excludes it."""
        _set_session(db_session)
        item = ServiceItemFactory(name="To Delete")
        item.soft_delete()
        db_session.commit()

        fetched = db_session.get(ServiceItem, item.id)
        assert fetched.is_deleted is True
        assert fetched.deleted_at is not None

        active = ServiceItem.not_deleted().all()
        assert item.id not in [i.id for i in active]


class TestServiceItemCustomFields:
    """Tests for the JSON custom_fields column."""

    def test_service_item_custom_fields(self, app, db_session):
        """JSON custom_fields stores and retrieves a dict correctly."""
        _set_session(db_session)
        custom = {"warranty_expires": "2026-12-31", "color": "blue"}
        item = ServiceItemFactory(
            name="Custom Fields Test",
            custom_fields=custom,
        )
        db_session.commit()
        db_session.refresh(item)

        fetched = db_session.get(ServiceItem, item.id)
        assert fetched.custom_fields is not None
        assert fetched.custom_fields["warranty_expires"] == "2026-12-31"
        assert fetched.custom_fields["color"] == "blue"


class TestServiceItemIsDrysuit:
    """Tests for the is_drysuit property."""

    def test_is_drysuit_true(self, app, db_session):
        """is_drysuit returns True when item_category is 'Drysuit'."""
        _set_session(db_session)
        item = ServiceItemFactory(name="My Drysuit", item_category="Drysuit")
        assert item.is_drysuit is True

    def test_is_drysuit_false(self, app, db_session):
        """is_drysuit returns False for non-drysuit categories."""
        _set_session(db_session)
        item = ServiceItemFactory(name="My BCD", item_category="BCD")
        assert item.is_drysuit is False
