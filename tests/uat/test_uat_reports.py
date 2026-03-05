"""UAT tests for reports (Phase 5)."""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


class TestReportsUAT:
    """Reports UAT tests."""

    def test_reports_hub(self, admin_page: Page, base_url: str):
        """Reports hub page loads with report cards."""
        admin_page.goto(f"{base_url}/reports/")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=Revenue")).to_be_visible()
        expect(admin_page.locator("text=Orders")).to_be_visible()

    def test_revenue_report(self, admin_page: Page, base_url: str):
        """Revenue report renders with charts."""
        admin_page.goto(f"{base_url}/reports/revenue")
        expect(admin_page.locator("h1")).to_contain_text("Revenue")

    def test_orders_report(self, admin_page: Page, base_url: str):
        """Service order report renders."""
        admin_page.goto(f"{base_url}/reports/orders")
        expect(admin_page.locator("h1")).to_contain_text("Order")

    def test_inventory_report(self, admin_page: Page, base_url: str):
        """Inventory report renders."""
        admin_page.goto(f"{base_url}/reports/inventory")
        expect(admin_page.locator("h1")).to_contain_text("Inventory")

    def test_customers_report(self, admin_page: Page, base_url: str):
        """Customer report renders."""
        admin_page.goto(f"{base_url}/reports/customers")
        expect(admin_page.locator("h1")).to_contain_text("Customer")

    def test_aging_report(self, admin_page: Page, base_url: str):
        """Aging report renders."""
        admin_page.goto(f"{base_url}/reports/aging")
        expect(admin_page.locator("h1")).to_contain_text("Aging")

    def test_reports_require_auth(self, page: Page, base_url: str):
        """Reports require authentication."""
        page.goto(f"{base_url}/reports/revenue")
        expect(page).to_have_url(re.compile(r".*/login.*"))
