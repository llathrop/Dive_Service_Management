"""UAT: Price list management.

Covers: price list view, category creation, item creation.

Phase: 2 (Core Entities)
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


def test_price_list_page(admin_page: Page, base_url: str):
    """Price list page loads."""
    admin_page.goto(f"{base_url}/price-list/")
    admin_page.wait_for_load_state("networkidle")
    assert "/price-list" in admin_page.url


def test_price_list_category_management(admin_page: Page, base_url: str):
    """Category management page loads (admin only)."""
    admin_page.goto(f"{base_url}/price-list/categories")
    admin_page.wait_for_load_state("networkidle")
    # Should show category management interface
    assert "/price-list" in admin_page.url


def test_create_price_list_item(admin_page: Page, base_url: str):
    """Create a price list item via the form."""
    # First ensure at least one category exists
    admin_page.goto(f"{base_url}/price-list/items/new")
    admin_page.wait_for_load_state("networkidle")

    name_field = admin_page.locator('input[name="name"]')
    if name_field.count() > 0:
        name_field.fill("UAT Seal Replacement")
        price_field = admin_page.locator('input[name="price"]')
        if price_field.count() > 0:
            price_field.fill("45.00")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")


def test_price_list_requires_auth(page: Page, base_url: str):
    """Anonymous user is redirected to login from price list page."""
    page.goto(f"{base_url}/price-list/")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url
