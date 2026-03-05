"""Unit tests for the customer service layer.

Tests cover paginated listing, search, filtering, CRUD operations,
soft-delete, and autocomplete-style search.
"""

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.services import customer_service

pytestmark = pytest.mark.unit


def _make_customer(db_session, **kwargs):
    """Create and persist a Customer with sensible defaults."""
    defaults = {
        "customer_type": "individual",
        "first_name": "Test",
        "last_name": "User",
    }
    defaults.update(kwargs)
    customer = Customer(**defaults)
    db_session.add(customer)
    db_session.commit()
    return customer


class TestGetCustomers:
    """Tests for get_customers()."""

    def test_get_customers_returns_paginated(self, app, db_session):
        """Creating 3 customers and fetching page 1 returns all three."""
        _make_customer(db_session, first_name="Alice", last_name="Adams")
        _make_customer(db_session, first_name="Bob", last_name="Brown")
        _make_customer(db_session, first_name="Carol", last_name="Clark")

        result = customer_service.get_customers(page=1, per_page=25)
        assert result.total == 3
        assert len(result.items) == 3

    def test_get_customers_excludes_deleted(self, app, db_session):
        """Soft-deleted customers are not returned by get_customers()."""
        c1 = _make_customer(db_session, first_name="Active", last_name="One")
        c2 = _make_customer(db_session, first_name="Deleted", last_name="Two")
        c2.soft_delete()
        db_session.commit()

        result = customer_service.get_customers()
        ids = [c.id for c in result.items]
        assert c1.id in ids
        assert c2.id not in ids

    def test_get_customers_search(self, app, db_session):
        """Search by name returns only matching customers."""
        _make_customer(db_session, first_name="Alice", last_name="Wonder")
        _make_customer(db_session, first_name="Bob", last_name="Builder")

        result = customer_service.get_customers(search="Alice")
        assert result.total == 1
        assert result.items[0].first_name == "Alice"

    def test_get_customers_filter_type(self, app, db_session):
        """Filtering by customer_type returns only matching type."""
        _make_customer(
            db_session,
            customer_type="individual",
            first_name="Jane",
            last_name="Doe",
        )
        _make_customer(
            db_session,
            customer_type="business",
            business_name="Dive Corp",
            first_name=None,
            last_name=None,
        )

        result = customer_service.get_customers(customer_type="business")
        assert result.total == 1
        assert result.items[0].business_name == "Dive Corp"


class TestGetCustomer:
    """Tests for get_customer()."""

    def test_get_customer_by_id(self, app, db_session):
        """get_customer() returns the correct customer by ID."""
        customer = _make_customer(
            db_session, first_name="Fetch", last_name="Me"
        )

        result = customer_service.get_customer(customer.id)
        assert result.id == customer.id
        assert result.first_name == "Fetch"

    def test_get_customer_not_found(self, app, db_session):
        """get_customer() raises 404 for a non-existent ID."""
        with pytest.raises(Exception) as exc_info:
            customer_service.get_customer(99999)
        assert exc_info.value.code == 404


class TestCreateCustomer:
    """Tests for create_customer()."""

    def test_create_customer(self, app, db_session):
        """create_customer() persists a customer with all provided fields."""
        data = {
            "customer_type": "individual",
            "first_name": "New",
            "last_name": "Customer",
            "email": "new@example.com",
            "phone_primary": "555-1234",
            "city": "Portland",
            "state_province": "OR",
        }
        customer = customer_service.create_customer(data)

        assert customer.id is not None
        assert customer.first_name == "New"
        assert customer.last_name == "Customer"
        assert customer.email == "new@example.com"
        assert customer.city == "Portland"

        # Verify persistence
        fetched = db_session.get(Customer, customer.id)
        assert fetched is not None
        assert fetched.email == "new@example.com"


class TestUpdateCustomer:
    """Tests for update_customer()."""

    def test_update_customer(self, app, db_session):
        """update_customer() updates fields correctly."""
        customer = _make_customer(
            db_session, first_name="Before", last_name="Update"
        )

        updated = customer_service.update_customer(
            customer.id,
            {"first_name": "After", "email": "updated@example.com"},
        )

        assert updated.first_name == "After"
        assert updated.email == "updated@example.com"
        assert updated.last_name == "Update"  # unchanged


class TestDeleteCustomer:
    """Tests for delete_customer()."""

    def test_delete_customer(self, app, db_session):
        """delete_customer() soft-deletes the customer."""
        customer = _make_customer(
            db_session, first_name="Delete", last_name="Me"
        )

        result = customer_service.delete_customer(customer.id)

        assert result.is_deleted is True
        assert result.deleted_at is not None

        # Verify it's excluded from not_deleted queries
        active = Customer.not_deleted().all()
        assert customer.id not in [c.id for c in active]


class TestSearchCustomers:
    """Tests for search_customers()."""

    def test_search_customers(self, app, db_session):
        """search_customers() returns matching results as dicts."""
        _make_customer(
            db_session,
            first_name="Alice",
            last_name="Diver",
            email="alice@dive.com",
        )
        _make_customer(
            db_session,
            first_name="Bob",
            last_name="Builder",
            email="bob@build.com",
        )

        results = customer_service.search_customers("Alice")
        assert len(results) == 1
        assert results[0]["display_name"] == "Alice Diver"
        assert results[0]["email"] == "alice@dive.com"
        assert "id" in results[0]
