"""Blueprint tests for global search routes.

Tests the global search results page and HTMX autocomplete endpoint.
Verifies that searches work across customers, service items, and
inventory items, and that anonymous access is properly restricted.
"""

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.service_item import ServiceItem


pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_customer(db_session, **overrides):
    """Create and persist a Customer with sensible defaults."""
    defaults = dict(
        customer_type="individual",
        first_name="Search",
        last_name="Customer",
        email="searchcust@example.com",
    )
    defaults.update(overrides)
    customer = Customer(**defaults)
    db.session.add(customer)
    db.session.commit()
    return customer


def _create_service_item(db_session, **overrides):
    """Create and persist a ServiceItem with sensible defaults."""
    if "customer_id" not in overrides:
        customer = _create_customer(db_session, email=f"itemowner-{id(overrides)}@example.com")
        overrides["customer_id"] = customer.id
    defaults = dict(
        name="Search Regulator",
        item_category="Regulator",
        serial_number="SEARCH-SN-001",
        brand="Apeks",
    )
    defaults.update(overrides)
    item = ServiceItem(**defaults)
    db.session.add(item)
    db.session.commit()
    return item


def _create_inventory_item(db_session, **overrides):
    """Create and persist an InventoryItem with sensible defaults."""
    defaults = dict(
        name="Search O-Ring",
        category="Parts",
        sku="SEARCH-SKU-001",
        quantity_in_stock=10,
        reorder_level=5,
        unit_of_measure="each",
        is_active=True,
    )
    defaults.update(overrides)
    item = InventoryItem(**defaults)
    db.session.add(item)
    db.session.commit()
    return item


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------

class TestAnonymousAccess:
    """Anonymous users are redirected to the login page."""

    def test_search_results_redirects(self, client):
        response = client.get("/search/?q=test")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_autocomplete_redirects(self, client):
        response = client.get("/search/autocomplete?q=test")
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Authenticated search (any role can search)
# ---------------------------------------------------------------------------

class TestSearchResults:
    """Verify the main search results page returns correct results."""

    def test_search_page_renders_with_no_query(self, logged_in_client):
        """Search page with no query parameter returns 200."""
        response = logged_in_client.get("/search/")
        assert response.status_code == 200

    def test_search_page_renders_with_empty_query(self, logged_in_client):
        """Search page with empty q returns 200 (no results)."""
        response = logged_in_client.get("/search/?q=")
        assert response.status_code == 200

    def test_search_requires_min_2_chars(self, logged_in_client, app, db_session):
        """Queries shorter than 2 chars should return no results."""
        with app.app_context():
            _create_customer(db_session, first_name="A")
        response = logged_in_client.get("/search/?q=A")
        assert response.status_code == 200
        # Single char search should not return results

    def test_search_finds_customer_by_name(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_customer(db_session, first_name="Findable", last_name="Diver")
        response = logged_in_client.get("/search/?q=Findable")
        assert response.status_code == 200
        assert b"Findable" in response.data

    def test_search_finds_customer_by_email(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_customer(db_session, email="unique-search@dive.com")
        response = logged_in_client.get("/search/?q=unique-search@dive")
        assert response.status_code == 200
        assert b"unique-search@dive.com" in response.data

    def test_search_finds_customer_by_phone(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_customer(
                db_session, phone_primary="555-9876"
            )
        response = logged_in_client.get("/search/?q=555-9876")
        assert response.status_code == 200
        assert b"555-9876" in response.data

    def test_search_finds_service_item_by_name(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            _create_service_item(db_session, name="UniqueReg2000")
        response = logged_in_client.get("/search/?q=UniqueReg2000")
        assert response.status_code == 200
        assert b"UniqueReg2000" in response.data

    def test_search_finds_service_item_by_serial(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            _create_service_item(
                db_session, serial_number="SN-GLOBAL-SEARCH"
            )
        response = logged_in_client.get("/search/?q=SN-GLOBAL-SEARCH")
        assert response.status_code == 200
        assert b"SN-GLOBAL-SEARCH" in response.data

    def test_search_finds_service_item_by_brand(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            _create_service_item(
                db_session,
                name="Brand Item",
                brand="ScubaPro",
                serial_number="SN-BRAND-001",
            )
        response = logged_in_client.get("/search/?q=ScubaPro")
        assert response.status_code == 200
        assert b"ScubaPro" in response.data

    def test_search_finds_inventory_by_name(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            _create_inventory_item(db_session, name="UniqueGasket99")
        response = logged_in_client.get("/search/?q=UniqueGasket99")
        assert response.status_code == 200
        assert b"UniqueGasket99" in response.data

    def test_search_finds_inventory_by_sku(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            _create_inventory_item(db_session, sku="GLOB-SKU-99")
        response = logged_in_client.get("/search/?q=GLOB-SKU-99")
        assert response.status_code == 200
        assert b"GLOB-SKU-99" in response.data

    def test_search_finds_inventory_by_manufacturer(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            _create_inventory_item(
                db_session,
                name="Mfg Part",
                manufacturer="DiveRite",
                sku="MFG-001",
            )
        response = logged_in_client.get("/search/?q=DiveRite")
        assert response.status_code == 200
        assert b"DiveRite" in response.data

    def test_search_excludes_deleted_customers(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            customer = _create_customer(
                db_session, first_name="DeletedSearch", last_name="Customer"
            )
            customer.soft_delete()
            db.session.commit()
        response = logged_in_client.get("/search/?q=DeletedSearch")
        assert response.status_code == 200
        # Soft-deleted customer should not appear in results; expect the
        # "No results found" message since there are no other matches.
        assert b"No results found" in response.data

    def test_search_excludes_deleted_items(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            item = _create_service_item(
                db_session, name="DeletedItem", serial_number="SN-DEL-001"
            )
            item.soft_delete()
            db.session.commit()
        response = logged_in_client.get("/search/?q=DeletedItem")
        assert response.status_code == 200
        # Soft-deleted item should not appear; expect "No results found"
        assert b"No results found" in response.data

    def test_search_excludes_deleted_inventory(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            item = _create_inventory_item(
                db_session, name="DeletedInv", sku="SKU-DEL-001"
            )
            item.soft_delete()
            db.session.commit()
        response = logged_in_client.get("/search/?q=DeletedInv")
        assert response.status_code == 200
        # Soft-deleted inventory item should not appear; expect "No results found"
        assert b"No results found" in response.data


# ---------------------------------------------------------------------------
# Autocomplete endpoint
# ---------------------------------------------------------------------------

class TestAutocomplete:
    """Verify the HTMX autocomplete endpoint."""

    def test_autocomplete_returns_200(self, logged_in_client):
        response = logged_in_client.get("/search/autocomplete?q=test")
        assert response.status_code == 200

    def test_autocomplete_with_short_query(self, logged_in_client):
        """Queries shorter than 2 chars should return empty results."""
        response = logged_in_client.get("/search/autocomplete?q=a")
        assert response.status_code == 200

    def test_autocomplete_finds_customer(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_customer(
                db_session, first_name="AutoComp", last_name="Customer"
            )
        response = logged_in_client.get("/search/autocomplete?q=AutoComp")
        assert response.status_code == 200
        assert b"AutoComp" in response.data

    def test_autocomplete_finds_service_item(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            _create_service_item(
                db_session, name="AutoItem", serial_number="SN-AUTO-001"
            )
        response = logged_in_client.get("/search/autocomplete?q=AutoItem")
        assert response.status_code == 200
        assert b"AutoItem" in response.data

    def test_autocomplete_finds_inventory(
        self, logged_in_client, app, db_session
    ):
        with app.app_context():
            _create_inventory_item(
                db_session, name="AutoInv", sku="AUTO-INV-001"
            )
        response = logged_in_client.get("/search/autocomplete?q=AutoInv")
        assert response.status_code == 200
        assert b"AutoInv" in response.data

    def test_autocomplete_empty_query(self, logged_in_client):
        response = logged_in_client.get("/search/autocomplete?q=")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Viewer and admin can also search
# ---------------------------------------------------------------------------

class TestOtherRolesCanSearch:
    """Verify viewer and admin roles can access search."""

    def test_viewer_can_search(self, viewer_client):
        response = viewer_client.get("/search/?q=test")
        assert response.status_code == 200

    def test_viewer_can_autocomplete(self, viewer_client):
        response = viewer_client.get("/search/autocomplete?q=test")
        assert response.status_code == 200

    def test_admin_can_search(self, admin_client):
        response = admin_client.get("/search/?q=test")
        assert response.status_code == 200

    def test_admin_can_autocomplete(self, admin_client):
        response = admin_client.get("/search/autocomplete?q=test")
        assert response.status_code == 200
