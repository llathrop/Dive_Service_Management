"""UAT tests for mobile quick-create dropdown functionality.

Verifies that the __new__ sentinel in select dropdowns correctly opens
the quick-create collapse section on mobile viewports.
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat

# iPhone 14 viewport
MOBILE_VIEWPORT = {"width": 375, "height": 812}


def _ensure_order_exists(page: Page, base_url: str) -> str:
    """Ensure at least one order exists and return its detail URL."""
    page.goto(f"{base_url}/orders/")
    page.wait_for_load_state("networkidle")

    first_link = page.locator("table tbody tr td a").first
    if first_link.is_visible():
        href = first_link.get_attribute("href")
        return f"{base_url}{href}" if not href.startswith("http") else href

    # Create a customer first
    page.goto(f"{base_url}/customers/new")
    page.fill('input[name="first_name"]', "Mobile")
    page.fill('input[name="last_name"]', "QCTest")
    page.fill('input[name="email"]', "mobile.qctest@test.com")
    page.click('button:has-text("Save Customer")')
    page.wait_for_load_state("networkidle")

    # Create an order
    page.goto(f"{base_url}/orders/new")
    page.select_option('select[name="customer_id"]', label="Mobile QCTest")
    page.fill('input[name="date_received"]', "2026-03-18")
    page.fill('textarea[name="description"]', "Mobile quick-create test order")
    page.click('button:has-text("Save Order")')
    page.wait_for_load_state("networkidle")
    return page.url


class TestMobileQuickCreate:
    """Mobile viewport tests for quick-create dropdown behaviour."""

    def test_mobile_service_item_quick_create_opens(
        self, admin_page: Page, base_url: str
    ):
        """Selecting __new__ from service item dropdown opens collapse on mobile."""
        order_url = _ensure_order_exists(admin_page, base_url)

        # Switch to mobile viewport
        admin_page.set_viewport_size(MOBILE_VIEWPORT)
        admin_page.goto(order_url)
        admin_page.wait_for_load_state("networkidle")

        # Expand the "Add Item" collapse form first
        add_btn = admin_page.locator('button:has-text("Add Item")')
        if add_btn.is_visible():
            add_btn.click()
            admin_page.wait_for_timeout(500)

        select_el = admin_page.locator("select#service_item_id")
        if not select_el.is_visible():
            pytest.skip("No service item select on this page (viewer role?)")

        # Select the __new__ sentinel
        select_el.select_option(value="__new__")
        admin_page.wait_for_timeout(600)

        # The quick-create collapse section should be visible
        section = admin_page.locator("#quickCreateItemSection")
        expect(section).to_be_visible()

    def test_mobile_service_item_quick_create_submit(
        self, admin_page: Page, base_url: str
    ):
        """Complete quick-create form on mobile and verify new option appears."""
        order_url = _ensure_order_exists(admin_page, base_url)

        admin_page.set_viewport_size(MOBILE_VIEWPORT)
        admin_page.goto(order_url)
        admin_page.wait_for_load_state("networkidle")

        # Open Add Item form
        add_btn = admin_page.locator('button:has-text("Add Item")')
        if add_btn.is_visible():
            add_btn.click()
            admin_page.wait_for_timeout(500)

        select_el = admin_page.locator("select#service_item_id")
        if not select_el.is_visible():
            pytest.skip("No service item select on this page (viewer role?)")

        # Select __new__ to open quick-create
        select_el.select_option(value="__new__")
        admin_page.wait_for_timeout(600)

        section = admin_page.locator("#quickCreateItemSection")
        expect(section).to_be_visible()

        # Fill out the quick-create form
        admin_page.fill("#qc_item_name", "Mobile Test Item")
        admin_page.select_option("#qc_item_category", value="Regulator")

        # Submit
        admin_page.click("#quickCreateItemSubmit")
        admin_page.wait_for_timeout(1000)

        # The new item should now be an option in the select
        options = select_el.locator("option")
        texts = options.all_text_contents()
        assert any("Mobile Test Item" in t for t in texts), (
            f"Expected 'Mobile Test Item' in select options, got: {texts}"
        )

    def test_mobile_quick_create_cancel(
        self, admin_page: Page, base_url: str
    ):
        """Open quick-create on mobile, click cancel, verify dropdown resets."""
        order_url = _ensure_order_exists(admin_page, base_url)

        admin_page.set_viewport_size(MOBILE_VIEWPORT)
        admin_page.goto(order_url)
        admin_page.wait_for_load_state("networkidle")

        # Open Add Item form
        add_btn = admin_page.locator('button:has-text("Add Item")')
        if add_btn.is_visible():
            add_btn.click()
            admin_page.wait_for_timeout(500)

        select_el = admin_page.locator("select#service_item_id")
        if not select_el.is_visible():
            pytest.skip("No service item select on this page (viewer role?)")

        # Select __new__
        select_el.select_option(value="__new__")
        admin_page.wait_for_timeout(600)

        section = admin_page.locator("#quickCreateItemSection")
        expect(section).to_be_visible()

        # Click cancel
        admin_page.click("#quickCreateItemCancel")
        admin_page.wait_for_timeout(500)

        # Section should be hidden and select should reset
        expect(section).not_to_be_visible()
        value = select_el.input_value()
        assert value != "__new__", "Select should reset after cancel"

    def test_mobile_quick_create_price_list(
        self, admin_page: Page, base_url: str
    ):
        """Verify price list quick-create collapse opens on mobile viewport."""
        order_url = _ensure_order_exists(admin_page, base_url)

        admin_page.set_viewport_size(MOBILE_VIEWPORT)
        admin_page.goto(order_url)
        admin_page.wait_for_load_state("networkidle")

        # Look for an order item's "Add Service" button (need at least one order item)
        add_service_btn = admin_page.locator(
            'button:has-text("Add Service")'
        ).first
        if not add_service_btn.is_visible():
            pytest.skip("No order items on this order to test price list quick-create")

        add_service_btn.click()
        admin_page.wait_for_timeout(500)

        # Find the price list select in the expanded service form
        price_select = admin_page.locator(
            'select[name="price_list_item_id"]'
        ).first
        if not price_select.is_visible():
            pytest.skip("Price list select not visible")

        # Select __new__
        price_select.select_option(value="__new__")
        admin_page.wait_for_timeout(600)

        # The quick-create collapse for price list should be visible
        price_section = admin_page.locator(
            '[id^="quickCreatePriceListSection-"]'
        ).first
        expect(price_section).to_be_visible()
