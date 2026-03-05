"""UAT: Service item management.

Covers: item list, create, detail, drysuit-specific fields, serial lookup.

Phase: 2 (Core Entities)
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


def test_item_list_page(admin_page: Page, base_url: str):
    """Service items list page loads."""
    admin_page.goto(f"{base_url}/items/")
    admin_page.wait_for_load_state("networkidle")
    assert "/items" in admin_page.url


def test_create_item_form_renders(admin_page: Page, base_url: str):
    """New service item form loads with expected fields."""
    admin_page.goto(f"{base_url}/items/new")
    admin_page.wait_for_load_state("networkidle")
    expect(admin_page.locator('input[name="name"]')).to_be_visible()
    expect(admin_page.locator('input[name="serial_number"]')).to_be_visible()


def test_create_service_item(admin_page: Page, base_url: str):
    """Create a non-drysuit service item."""
    admin_page.goto(f"{base_url}/items/new")
    admin_page.wait_for_load_state("networkidle")

    admin_page.fill('input[name="name"]', "UAT Test Regulator")
    admin_page.fill('input[name="serial_number"]', "UAT-REG-001")

    # Select category if it's a select field
    category = admin_page.locator('select[name="item_category"]')
    if category.count() > 0:
        category.select_option(label="Regulator")
    else:
        admin_page.fill('input[name="item_category"]', "Regulator")

    admin_page.click('button[type="submit"]')
    admin_page.wait_for_load_state("networkidle")

    page_text = admin_page.text_content("body")
    assert "UAT Test Regulator" in page_text


def test_create_drysuit_item(admin_page: Page, base_url: str):
    """Create a drysuit service item with drysuit-specific fields."""
    admin_page.goto(f"{base_url}/items/new")
    admin_page.wait_for_load_state("networkidle")

    admin_page.fill('input[name="name"]', "UAT DUI CF200X Drysuit")
    admin_page.fill('input[name="serial_number"]', "UAT-DS-001")

    # Select Drysuit category
    category = admin_page.locator('select[name="item_category"]')
    if category.count() > 0:
        category.select_option(label="Drysuit")

    # Fill drysuit-specific fields if visible
    brand_field = admin_page.locator('input[name="brand"]')
    if brand_field.count() > 0:
        brand_field.fill("DUI")

    model_field = admin_page.locator('input[name="model"]')
    if model_field.count() > 0:
        model_field.fill("CF200X")

    admin_page.click('button[type="submit"]')
    admin_page.wait_for_load_state("networkidle")

    page_text = admin_page.text_content("body")
    assert "UAT DUI CF200X" in page_text


def test_item_lookup_page(admin_page: Page, base_url: str):
    """Serial number lookup page loads."""
    admin_page.goto(f"{base_url}/items/lookup")
    admin_page.wait_for_load_state("networkidle")
    # Should have a search input
    search = admin_page.locator('input[name="serial_number"], input[name="q"], input[type="search"]')
    assert search.count() > 0


def test_item_list_requires_auth(page: Page, base_url: str):
    """Anonymous user is redirected to login from items page."""
    page.goto(f"{base_url}/items/")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url
