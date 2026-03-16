"""Tests for the enhanced search blueprint (autocomplete endpoint)."""

import pytest

from tests.factories import (
    CustomerFactory,
    InventoryItemFactory,
    InvoiceFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
)


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


class TestAutocompleteEndpoint:
    """Tests for GET /search/autocomplete."""

    def test_autocomplete_requires_authentication(self, client):
        resp = client.get("/search/autocomplete?q=test")
        # Should redirect to login or return 401/302
        assert resp.status_code in (302, 401)

    def test_autocomplete_returns_html(self, logged_in_client, db_session):
        resp = logged_in_client.get("/search/autocomplete?q=test")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")

    def test_autocomplete_short_query_returns_no_entity_results(self, logged_in_client, db_session):
        resp = logged_in_client.get("/search/autocomplete?q=a")
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        # Should not contain any entity category headers
        assert "Customers" not in data
        assert "Orders" not in data
        assert "Inventory" not in data

    def test_autocomplete_empty_query_returns_empty(self, logged_in_client, db_session):
        resp = logged_in_client.get("/search/autocomplete?q=")
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        assert "list-group-item-action" not in data

    def test_autocomplete_finds_customer(self, logged_in_client, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(first_name="Autocomplete", last_name="Testuser")

        resp = logged_in_client.get("/search/autocomplete?q=Autocomplete")
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        assert "Autocomplete" in data
        assert "Customers" in data

    def test_autocomplete_finds_order(self, logged_in_client, app, db_session):
        _set_sessions(db_session)
        ServiceOrderFactory(order_number="SO-AUTO-12345")

        resp = logged_in_client.get("/search/autocomplete?q=SO-AUTO-12345")
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        assert "SO-AUTO-12345" in data
        assert "Orders" in data

    def test_autocomplete_finds_inventory(self, logged_in_client, app, db_session):
        _set_sessions(db_session)
        InventoryItemFactory(name="Autocomplete Widget XYZ")

        resp = logged_in_client.get("/search/autocomplete?q=Autocomplete Widget")
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        assert "Autocomplete Widget" in data
        assert "Inventory" in data

    def test_autocomplete_no_results_shows_message(self, logged_in_client, db_session):
        resp = logged_in_client.get(
            "/search/autocomplete?q=zzz_definitely_not_found_zzz"
        )
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        assert "No results found" in data

    def test_autocomplete_view_all_link(self, logged_in_client, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(first_name="Viewall", last_name="Test")

        resp = logged_in_client.get("/search/autocomplete?q=Viewall")
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        assert "View all results" in data


class TestSearchResultsPage:
    """Tests for GET /search/."""

    def test_results_requires_authentication(self, client):
        resp = client.get("/search/?q=test")
        assert resp.status_code in (302, 401)

    def test_results_page_loads(self, logged_in_client, db_session):
        resp = logged_in_client.get("/search/?q=test")
        assert resp.status_code == 200

    def test_results_shows_orders_section(self, logged_in_client, app, db_session):
        _set_sessions(db_session)
        ServiceOrderFactory(order_number="SO-RESULTS-001")

        resp = logged_in_client.get("/search/?q=SO-RESULTS-001")
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        assert "SO-RESULTS-001" in data
        assert "Orders" in data

    def test_results_shows_invoices_section(self, logged_in_client, app, db_session):
        _set_sessions(db_session)
        InvoiceFactory(invoice_number="INV-RESULTS-001")

        resp = logged_in_client.get("/search/?q=INV-RESULTS-001")
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        assert "INV-RESULTS-001" in data
        assert "Invoices" in data
