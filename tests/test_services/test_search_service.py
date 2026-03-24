"""Tests for the search service layer."""

import pytest

from app.services import search_service
from tests.factories import (
    CustomerFactory,
    InventoryItemFactory,
    InvoiceFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
)

pytestmark = pytest.mark.unit


def _set_sessions(db_session):
    """Set the SQLAlchemy session on all factories used in these tests."""
    for factory_cls in [
        CustomerFactory,
        InventoryItemFactory,
        InvoiceFactory,
        ServiceItemFactory,
        ServiceOrderFactory,
    ]:
        factory_cls._meta.sqlalchemy_session = db_session


class TestGlobalSearch:
    """Tests for search_service.global_search()."""

    def test_global_search_returns_all_keys(self, app, db_session):
        results = search_service.global_search("test")
        assert "customers" in results
        assert "service_items" in results
        assert "inventory_items" in results
        assert "orders" in results
        assert "invoices" in results

    def test_global_search_empty_query_returns_empty(self, app, db_session):
        results = search_service.global_search("")
        for key in results:
            assert results[key] == []

    def test_global_search_short_query_returns_empty(self, app, db_session):
        results = search_service.global_search("a")
        for key in results:
            assert results[key] == []

    def test_global_search_none_query_returns_empty(self, app, db_session):
        results = search_service.global_search(None)
        for key in results:
            assert results[key] == []

    def test_global_search_whitespace_query_returns_empty(self, app, db_session):
        results = search_service.global_search("  ")
        for key in results:
            assert results[key] == []


class TestSearchCustomers:
    """Tests for search_service.search_customers()."""

    def test_finds_customer_by_first_name(self, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(first_name="Alphonse", last_name="Doe")

        results = search_service.search_customers("Alphonse")
        assert len(results) == 1
        assert results[0]["entity_type"] == "customer"
        assert "Alphonse" in results[0]["display_text"]

    def test_finds_customer_by_last_name(self, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(first_name="Jane", last_name="Zephyrton")

        results = search_service.search_customers("Zephyrton")
        assert len(results) == 1
        assert results[0]["url"] is not None

    def test_finds_customer_by_email(self, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(email="unique-search-test@example.com")

        results = search_service.search_customers("unique-search-test")
        assert len(results) == 1

    def test_finds_business_customer(self, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(business=True, business_name="Oceanic Diving Co")

        results = search_service.search_customers("Oceanic Diving")
        assert len(results) == 1
        assert "Oceanic Diving" in results[0]["display_text"]

    def test_no_results_returns_empty(self, app, db_session):
        results = search_service.search_customers("zzz_nonexistent_zzz")
        assert results == []

    def test_result_has_url(self, app, db_session):
        _set_sessions(db_session)
        c = CustomerFactory(first_name="Urltest", last_name="Customer")

        results = search_service.search_customers("Urltest")
        assert len(results) == 1
        assert results[0]["url"] == f"/customers/{c.id}"


class TestSearchOrders:
    """Tests for search_service.search_orders()."""

    def test_finds_order_by_order_number(self, app, db_session):
        _set_sessions(db_session)
        ServiceOrderFactory(order_number="SO-2026-99999")

        results = search_service.search_orders("SO-2026-99999")
        assert len(results) == 1
        assert results[0]["entity_type"] == "order"
        assert "SO-2026-99999" in results[0]["display_text"]

    def test_finds_order_by_description(self, app, db_session):
        _set_sessions(db_session)
        ServiceOrderFactory(
            order_number="SO-2026-88888",
            description="Regulator annual service unique-desc",
        )

        results = search_service.search_orders("unique-desc")
        assert len(results) == 1

    def test_order_result_has_status(self, app, db_session):
        _set_sessions(db_session)
        ServiceOrderFactory(order_number="SO-2026-77777", status="in_progress")

        results = search_service.search_orders("SO-2026-77777")
        assert results[0]["status"] == "in_progress"

    def test_empty_query_returns_empty(self, app, db_session):
        results = search_service.search_orders("")
        assert results == []


class TestSearchInventory:
    """Tests for search_service.search_inventory_items()."""

    def test_finds_inventory_by_name(self, app, db_session):
        _set_sessions(db_session)
        InventoryItemFactory(name="Turbo O-Ring Set")

        results = search_service.search_inventory_items("Turbo O-Ring")
        assert len(results) == 1
        assert results[0]["entity_type"] == "inventory_item"

    def test_finds_inventory_by_sku(self, app, db_session):
        _set_sessions(db_session)
        InventoryItemFactory(sku="SKU-UNIQUE-42")

        results = search_service.search_inventory_items("UNIQUE-42")
        assert len(results) == 1

    def test_result_contains_url(self, app, db_session):
        _set_sessions(db_session)
        item = InventoryItemFactory(name="Searchable Widget")

        results = search_service.search_inventory_items("Searchable Widget")
        assert results[0]["url"] == f"/inventory/{item.id}"


class TestSearchInvoices:
    """Tests for search_service.search_invoices()."""

    def test_finds_invoice_by_number(self, app, db_session):
        _set_sessions(db_session)
        InvoiceFactory(invoice_number="INV-2026-55555")

        results = search_service.search_invoices("INV-2026-55555")
        assert len(results) == 1
        assert results[0]["entity_type"] == "invoice"
        assert "INV-2026-55555" in results[0]["display_text"]

    def test_invoice_result_has_status(self, app, db_session):
        _set_sessions(db_session)
        InvoiceFactory(invoice_number="INV-2026-44444", status="sent")

        results = search_service.search_invoices("INV-2026-44444")
        assert results[0]["status"] == "sent"


class TestSearchServiceItems:
    """Tests for search_service.search_service_items()."""

    def test_finds_item_by_name(self, app, db_session):
        _set_sessions(db_session)
        ServiceItemFactory(name="Aqualung Legend LX")

        results = search_service.search_service_items("Aqualung Legend")
        assert len(results) == 1
        assert results[0]["entity_type"] == "service_item"

    def test_finds_item_by_serial(self, app, db_session):
        _set_sessions(db_session)
        ServiceItemFactory(name="Some Reg", serial_number="SN-UNIQUE-789")

        results = search_service.search_service_items("SN-UNIQUE-789")
        assert len(results) == 1
        assert "SN-UNIQUE-789" in results[0]["display_text"]


class TestResultsCategorized:
    """Tests verifying results are correctly categorized."""

    def test_results_grouped_by_entity_type(self, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(first_name="Searchterm", last_name="Test")
        InventoryItemFactory(name="Searchterm Widget")
        ServiceOrderFactory(
            order_number="SO-SEARCHTERM-001",
            description="Searchterm in description",
        )

        results = search_service.global_search("Searchterm", limit=10)
        assert len(results["customers"]) >= 1
        assert len(results["inventory_items"]) >= 1
        assert len(results["orders"]) >= 1

        # Verify entity_type is correct in each group
        for c in results["customers"]:
            assert c["entity_type"] == "customer"
        for i in results["inventory_items"]:
            assert i["entity_type"] == "inventory_item"
        for o in results["orders"]:
            assert o["entity_type"] == "order"
