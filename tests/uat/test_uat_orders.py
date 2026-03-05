"""UAT tests for service order management (Phase 3)."""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


class TestOrdersUAT:
    """Service order workflow UAT tests."""

    def test_order_list_page(self, admin_page: Page, base_url: str):
        """Verify orders list page loads."""
        admin_page.goto(f"{base_url}/orders/")
        expect(admin_page.locator("h1")).to_contain_text("Service Orders")

    def test_create_service_order(self, admin_page: Page, base_url: str):
        """Create a service order with required fields."""
        # First ensure a customer exists
        admin_page.goto(f"{base_url}/customers/new")
        admin_page.fill('input[name="first_name"]', "UAT")
        admin_page.fill('input[name="last_name"]', "OrderTest")
        admin_page.fill('input[name="email"]', "uat.order@test.com")
        admin_page.click('button:has-text("Save Customer")')
        admin_page.wait_for_load_state("networkidle")

        # Create order
        admin_page.goto(f"{base_url}/orders/new")
        admin_page.select_option('select[name="customer_id"]', label="UAT OrderTest")
        admin_page.fill('input[name="date_received"]', "2026-03-04")
        admin_page.fill('textarea[name="description"]', "UAT test order")
        admin_page.click('button:has-text("Save Order")')
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page).to_have_url(re.compile(r".*/orders/\d+"))
        expect(admin_page.locator("h1")).to_contain_text("SO-")

    def test_order_detail_shows_sections(self, admin_page: Page, base_url: str):
        """Verify order detail page shows all sections."""
        admin_page.goto(f"{base_url}/orders/")
        # Click first order if one exists
        first_link = admin_page.locator("table tbody tr td a").first
        if first_link.is_visible():
            first_link.click()
            admin_page.wait_for_load_state("networkidle")
            expect(admin_page.locator("text=Service Items")).to_be_visible()
            expect(admin_page.locator("text=Financial Summary")).to_be_visible()

    def test_order_status_transition(self, admin_page: Page, base_url: str):
        """Verify order status can be changed."""
        admin_page.goto(f"{base_url}/orders/")
        first_link = admin_page.locator("table tbody tr td a").first
        if first_link.is_visible():
            first_link.click()
            admin_page.wait_for_load_state("networkidle")
            # Look for Change Status dropdown
            expect(admin_page.locator("text=Change Status")).to_be_visible()

    def test_orders_require_auth(self, page: Page, base_url: str):
        """Verify orders page redirects to login when not authenticated."""
        page.goto(f"{base_url}/orders/")
        expect(page).to_have_url(re.compile(r".*/login.*"))

    def test_viewer_cannot_create_order(self, viewer_page: Page, base_url: str):
        """Viewer role cannot create orders."""
        viewer_page.goto(f"{base_url}/orders/new")
        # Should get 403 or redirect
        content = viewer_page.content()
        assert "403" in content or "/login" in viewer_page.url or "Forbidden" in content
