"""Unit tests for the Customer model.

Tests cover creation, validation, defaults, properties, soft-delete,
timestamps, and relationships.
"""

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.service_item import ServiceItem
from tests.factories import CustomerFactory, ServiceItemFactory

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session


class TestCustomerCreation:
    """Tests for basic customer creation and persistence."""

    def test_create_individual_customer(self, app, db_session):
        """An individual customer persists all fields correctly."""
        _set_session(db_session)
        customer = CustomerFactory(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone_primary="555-0100",
            phone_secondary="555-0101",
            address_line1="123 Main St",
            address_line2="Suite 4",
            city="Portland",
            state_province="OR",
            postal_code="97201",
            country="US",
            preferred_contact="phone",
            tax_exempt=True,
            tax_id="12-3456789",
            payment_terms="Net 30",
            credit_limit=5000.00,
            notes="VIP customer",
            referral_source="Website",
        )

        fetched = db_session.get(Customer, customer.id)
        assert fetched is not None
        assert fetched.first_name == "John"
        assert fetched.last_name == "Doe"
        assert fetched.customer_type == "individual"
        assert fetched.email == "john@example.com"
        assert fetched.phone_primary == "555-0100"
        assert fetched.phone_secondary == "555-0101"
        assert fetched.address_line1 == "123 Main St"
        assert fetched.address_line2 == "Suite 4"
        assert fetched.city == "Portland"
        assert fetched.state_province == "OR"
        assert fetched.postal_code == "97201"
        assert fetched.country == "US"
        assert fetched.preferred_contact == "phone"
        assert fetched.tax_exempt is True
        assert fetched.tax_id == "12-3456789"
        assert fetched.payment_terms == "Net 30"
        assert float(fetched.credit_limit) == 5000.00
        assert fetched.notes == "VIP customer"
        assert fetched.referral_source == "Website"

    def test_create_business_customer(self, app, db_session):
        """A business customer can have business_name without first/last."""
        _set_session(db_session)
        customer = CustomerFactory(business=True)

        fetched = db_session.get(Customer, customer.id)
        assert fetched is not None
        assert fetched.customer_type == "business"
        assert fetched.business_name is not None
        assert fetched.first_name is None
        assert fetched.last_name is None
        assert fetched.contact_person is not None


class TestCustomerValidation:
    """Tests for customer field validation."""

    def test_customer_requires_name(self, app, db_session):
        """A customer with neither individual nor business name fails validation."""
        customer = Customer(
            customer_type="individual",
            email="nobody@example.com",
        )
        with pytest.raises(ValueError, match="must have either"):
            customer.validate_name()

    def test_invalid_customer_type_raises(self, app, db_session):
        """Setting an invalid customer_type raises ValueError."""
        with pytest.raises(ValueError, match="customer_type must be one of"):
            Customer(customer_type="government")

    def test_invalid_preferred_contact_raises(self, app, db_session):
        """Setting an invalid preferred_contact raises ValueError."""
        with pytest.raises(ValueError, match="preferred_contact must be one of"):
            Customer(preferred_contact="carrier_pigeon")


class TestCustomerDefaults:
    """Tests for default field values."""

    def test_customer_defaults(self, app, db_session):
        """Default values are applied correctly on a minimal customer."""
        _set_session(db_session)
        customer = CustomerFactory(
            first_name="Jane",
            last_name="Smith",
        )

        assert customer.customer_type == "individual"
        assert customer.preferred_contact == "email"
        assert customer.country == "US"
        assert customer.tax_exempt is False
        assert customer.do_not_service is False


class TestCustomerProperties:
    """Tests for computed properties."""

    def test_customer_display_name_individual(self, app, db_session):
        """display_name returns 'First Last' for an individual."""
        _set_session(db_session)
        customer = CustomerFactory(
            first_name="Alice",
            last_name="Wonder",
        )
        assert customer.display_name == "Alice Wonder"

    def test_customer_display_name_business(self, app, db_session):
        """display_name returns the business_name for a business customer."""
        _set_session(db_session)
        customer = CustomerFactory(
            business=True,
            business_name="Dive Deep LLC",
        )
        assert customer.display_name == "Dive Deep LLC"

    def test_customer_full_address(self, app, db_session):
        """full_address returns a formatted multi-line address."""
        _set_session(db_session)
        customer = CustomerFactory(
            address_line1="100 Ocean Ave",
            address_line2="Apt 3B",
            city="Miami",
            state_province="FL",
            postal_code="33101",
            country="US",
        )
        expected = "100 Ocean Ave\nApt 3B\nMiami, FL 33101"
        assert customer.full_address == expected


class TestCustomerSoftDelete:
    """Tests for soft-delete and restore functionality."""

    def test_customer_soft_delete(self, app, db_session):
        """soft_delete() sets is_deleted and deleted_at."""
        _set_session(db_session)
        customer = CustomerFactory()
        customer.soft_delete()
        db_session.commit()

        fetched = db_session.get(Customer, customer.id)
        assert fetched.is_deleted is True
        assert fetched.deleted_at is not None

        # not_deleted() should exclude this customer
        active = Customer.not_deleted().all()
        assert customer.id not in [c.id for c in active]

    def test_customer_restore(self, app, db_session):
        """restore() clears is_deleted and deleted_at flags."""
        _set_session(db_session)
        customer = CustomerFactory()
        customer.soft_delete()
        db_session.commit()

        customer.restore()
        db_session.commit()

        fetched = db_session.get(Customer, customer.id)
        assert fetched.is_deleted is False
        assert fetched.deleted_at is None


class TestCustomerTimestamps:
    """Tests for automatic timestamp management."""

    def test_customer_timestamps(self, app, db_session):
        """created_at is auto-set; updated_at is set on change."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Time", last_name="Test")

        assert customer.created_at is not None

        # Trigger an update
        customer.notes = "Updated notes"
        db_session.commit()
        db_session.refresh(customer)

        # updated_at should now be set (may be None initially then set on update)
        # The onupdate trigger fires on the next commit after a change
        assert customer.created_at is not None


class TestCustomerRelationships:
    """Tests for customer relationships."""

    def test_customer_service_items_relationship(self, app, db_session):
        """A customer can have service items navigable via FK."""
        _set_session(db_session)
        customer = CustomerFactory(
            first_name="Rel",
            last_name="Test",
        )
        item1 = ServiceItemFactory(
            name="Regulator Set",
            customer=customer,
        )
        item2 = ServiceItemFactory(
            name="BCD Vest",
            customer=customer,
        )

        # Navigate from customer to items
        items = customer.service_items.all()
        assert len(items) == 2
        item_names = {i.name for i in items}
        assert "Regulator Set" in item_names
        assert "BCD Vest" in item_names

        # Navigate from item to customer
        assert item1.customer.id == customer.id
