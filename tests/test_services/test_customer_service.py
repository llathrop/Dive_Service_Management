"""Tests for the customer service layer."""

import pytest
from werkzeug.exceptions import NotFound

from app.services import customer_service
from tests.factories import CustomerFactory

pytestmark = pytest.mark.unit


class TestGetCustomers:
    """Tests for customer_service.get_customers()."""

    def test_returns_paginated_results(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        CustomerFactory.create_batch(3)

        result = customer_service.get_customers(page=1, per_page=25)
        assert result.total == 3
        assert len(result.items) == 3

    def test_search_filters_by_name(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        CustomerFactory(first_name="Alice", last_name="Smith")
        CustomerFactory(first_name="Bob", last_name="Jones")

        result = customer_service.get_customers(search="Alice")
        assert result.total == 1
        assert result.items[0].first_name == "Alice"

    def test_search_filters_by_email(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        CustomerFactory(email="unique-test@example.com")
        CustomerFactory(email="other@example.com")

        result = customer_service.get_customers(search="unique-test")
        assert result.total == 1

    def test_customer_type_filter(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        CustomerFactory(customer_type="individual")
        CustomerFactory(business=True)

        result = customer_service.get_customers(customer_type="business")
        assert result.total == 1
        assert result.items[0].customer_type == "business"

    def test_excludes_soft_deleted(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        c = CustomerFactory()
        c.soft_delete()
        db_session.commit()

        result = customer_service.get_customers()
        assert result.total == 0

    def test_sorting_asc(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        CustomerFactory(last_name="Zebra")
        CustomerFactory(last_name="Apple")

        result = customer_service.get_customers(sort="last_name", order="asc")
        names = [c.last_name for c in result.items]
        assert names == ["Apple", "Zebra"]

    def test_sorting_desc(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        CustomerFactory(last_name="Zebra")
        CustomerFactory(last_name="Apple")

        result = customer_service.get_customers(sort="last_name", order="desc")
        names = [c.last_name for c in result.items]
        assert names == ["Zebra", "Apple"]


class TestGetCustomer:
    """Tests for customer_service.get_customer()."""

    def test_returns_customer_by_id(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        customer = CustomerFactory()

        result = customer_service.get_customer(customer.id)
        assert result.id == customer.id

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            customer_service.get_customer(9999)

    def test_raises_404_for_soft_deleted(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        customer = CustomerFactory()
        customer.soft_delete()
        db_session.commit()

        with pytest.raises(NotFound):
            customer_service.get_customer(customer.id)


class TestCreateCustomer:
    """Tests for customer_service.create_customer()."""

    def test_creates_individual_customer(self, app, db_session):
        data = {
            "customer_type": "individual",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
        }
        customer = customer_service.create_customer(data, created_by=1)
        assert customer.id is not None
        assert customer.first_name == "Jane"
        assert customer.created_by == 1

    def test_creates_business_customer(self, app, db_session):
        data = {
            "customer_type": "business",
            "business_name": "Dive Shop LLC",
        }
        customer = customer_service.create_customer(data)
        assert customer.business_name == "Dive Shop LLC"


class TestUpdateCustomer:
    """Tests for customer_service.update_customer()."""

    def test_updates_fields(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        customer = CustomerFactory(first_name="Old")

        result = customer_service.update_customer(
            customer.id, {"first_name": "New"}
        )
        assert result.first_name == "New"

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            customer_service.update_customer(9999, {"first_name": "Test"})


class TestDeleteCustomer:
    """Tests for customer_service.delete_customer()."""

    def test_soft_deletes_customer(self, app, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        customer = CustomerFactory()

        result = customer_service.delete_customer(customer.id)
        assert result.is_deleted is True

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            customer_service.delete_customer(9999)
