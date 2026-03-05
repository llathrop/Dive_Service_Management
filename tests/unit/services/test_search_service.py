"""Unit tests for the search service layer.

Tests cover global search across customers, service items, and inventory,
as well as exclusion of soft-deleted entities.
"""

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.service_item import ServiceItem
from app.services import search_service

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


def _make_service_item(db_session, **kwargs):
    """Create and persist a ServiceItem with sensible defaults."""
    defaults = {
        "name": "Test Equipment",
    }
    defaults.update(kwargs)
    item = ServiceItem(**defaults)
    db_session.add(item)
    db_session.commit()
    return item


def _make_inventory_item(db_session, **kwargs):
    """Create and persist an InventoryItem with sensible defaults."""
    defaults = {
        "name": "Test Part",
        "category": "General",
    }
    defaults.update(kwargs)
    item = InventoryItem(**defaults)
    db_session.add(item)
    db_session.commit()
    return item


class TestGlobalSearch:
    """Tests for global_search()."""

    def test_global_search_finds_customers(self, app, db_session):
        """Global search returns matching customers."""
        _make_customer(
            db_session,
            first_name="Alice",
            last_name="Diver",
            email="alice@dive.com",
        )

        results = search_service.global_search("Alice")
        assert len(results["customers"]) == 1
        assert results["customers"][0]["display_name"] == "Alice Diver"
        assert results["customers"][0]["type"] == "customer"

    def test_global_search_finds_service_items(self, app, db_session):
        """Global search returns matching service items."""
        _make_service_item(
            db_session,
            name="Apeks XTX50",
            brand="Apeks",
            serial_number="APX-12345",
        )

        results = search_service.global_search("Apeks")
        assert len(results["service_items"]) == 1
        assert results["service_items"][0]["name"] == "Apeks XTX50"
        assert results["service_items"][0]["type"] == "service_item"

    def test_global_search_finds_inventory(self, app, db_session):
        """Global search returns matching inventory items."""
        _make_inventory_item(
            db_session,
            name="Latex Neck Seal",
            sku="SEAL-001",
            manufacturer="DUI",
        )

        results = search_service.global_search("Latex")
        assert len(results["inventory_items"]) == 1
        assert results["inventory_items"][0]["name"] == "Latex Neck Seal"
        assert results["inventory_items"][0]["type"] == "inventory_item"

    def test_global_search_no_results(self, app, db_session):
        """Global search returns empty lists when nothing matches."""
        results = search_service.global_search("nonexistent-xyz")
        assert results["customers"] == []
        assert results["service_items"] == []
        assert results["inventory_items"] == []

    def test_global_search_empty_query(self, app, db_session):
        """Empty query returns empty results."""
        _make_customer(db_session, first_name="Alice", last_name="Test")

        results = search_service.global_search("")
        assert results["customers"] == []
        assert results["service_items"] == []
        assert results["inventory_items"] == []


class TestSearchExcludesDeleted:
    """Tests that search excludes soft-deleted entities."""

    def test_search_excludes_deleted(self, app, db_session):
        """Soft-deleted entities are not returned by search functions."""
        # Create and soft-delete a customer
        customer = _make_customer(
            db_session, first_name="Deleted", last_name="Customer"
        )
        customer.soft_delete()
        db_session.commit()

        # Create and soft-delete a service item
        service_item = _make_service_item(
            db_session, name="Deleted Equipment"
        )
        service_item.soft_delete()
        db_session.commit()

        # Create and soft-delete an inventory item
        inventory_item = _make_inventory_item(
            db_session, name="Deleted Part"
        )
        inventory_item.soft_delete()
        db_session.commit()

        # Global search should not find any of them
        results = search_service.global_search("Deleted")
        assert results["customers"] == []
        assert results["service_items"] == []
        assert results["inventory_items"] == []

        # Individual searches should also exclude them
        assert search_service.search_customers("Deleted") == []
        assert search_service.search_service_items("Deleted") == []
        assert search_service.search_inventory_items("Deleted") == []
