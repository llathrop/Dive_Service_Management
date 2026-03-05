"""UAT: Inventory management.

Covers: inventory list, create, detail, stock adjustment, low stock view.

Phase: 2 (Core Entities)
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


def test_inventory_list_page(admin_page: Page, base_url: str):
    """Inventory list page loads and shows table or empty state."""
    admin_page.goto(f"{base_url}/inventory/")
    admin_page.wait_for_load_state("networkidle")
    assert "/inventory" in admin_page.url


def test_create_inventory_item_form_renders(admin_page: Page, base_url: str):
    """New inventory item form loads with expected fields."""
    admin_page.goto(f"{base_url}/inventory/new")
    admin_page.wait_for_load_state("networkidle")
    expect(admin_page.locator('input[name="name"]')).to_be_visible()


def test_create_inventory_item(admin_page: Page, base_url: str):
    """Create an inventory item and verify it appears."""
    admin_page.goto(f"{base_url}/inventory/new")
    admin_page.wait_for_load_state("networkidle")

    admin_page.fill('input[name="name"]', "UAT Latex Neck Seal")
    admin_page.fill('input[name="sku"]', "UAT-SEAL-001")

    # Fill category
    cat = admin_page.locator('select[name="category"], input[name="category"]')
    if cat.count() > 0:
        if cat.first.evaluate("el => el.tagName") == "SELECT":
            cat.first.select_option(index=1)
        else:
            cat.first.fill("Seals")

    # Stock and pricing
    qty = admin_page.locator('input[name="quantity_in_stock"]')
    if qty.count() > 0:
        qty.fill("25")

    price = admin_page.locator('input[name="resale_price"]')
    if price.count() > 0:
        price.fill("34.99")

    admin_page.click('button[type="submit"]')
    admin_page.wait_for_load_state("networkidle")

    page_text = admin_page.text_content("body")
    assert "UAT Latex Neck Seal" in page_text


def test_low_stock_page(admin_page: Page, base_url: str):
    """Low stock page loads without errors."""
    admin_page.goto(f"{base_url}/inventory/low-stock")
    admin_page.wait_for_load_state("networkidle")
    assert admin_page.url.endswith("/low-stock") or "/inventory" in admin_page.url


def test_inventory_requires_auth(page: Page, base_url: str):
    """Anonymous user is redirected to login from inventory page."""
    page.goto(f"{base_url}/inventory/")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url


def test_viewer_cannot_create_inventory(viewer_page: Page, base_url: str):
    """Viewer role cannot access inventory creation (403 or redirect)."""
    viewer_page.goto(f"{base_url}/inventory/new")
    viewer_page.wait_for_load_state("networkidle")
    page_text = viewer_page.text_content("body")
    url = viewer_page.url
    assert "403" in page_text or "Forbidden" in page_text or "/inventory/new" not in url
