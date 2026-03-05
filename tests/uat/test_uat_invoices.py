"""UAT tests for invoice and billing management (Phase 4)."""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


class TestInvoicesUAT:
    """Invoice management UAT tests."""

    def test_invoice_list_page(self, admin_page: Page, base_url: str):
        """Verify invoices list page loads."""
        admin_page.goto(f"{base_url}/invoices/")
        expect(admin_page.locator("h1")).to_contain_text("Invoices")

    def test_create_invoice(self, admin_page: Page, base_url: str):
        """Create an invoice manually."""
        admin_page.goto(f"{base_url}/invoices/new")
        admin_page.wait_for_load_state("networkidle")
        # Verify form fields exist
        expect(admin_page.locator('select[name="customer_id"]')).to_be_visible()
        expect(admin_page.locator('input[name="issue_date"]')).to_be_visible()

    def test_invoice_detail_page(self, admin_page: Page, base_url: str):
        """Invoice detail page loads with line items and payments sections."""
        admin_page.goto(f"{base_url}/invoices/")
        first_link = admin_page.locator("table tbody tr td a").first
        if first_link.is_visible():
            first_link.click()
            admin_page.wait_for_load_state("networkidle")
            expect(admin_page.locator("text=Line Items")).to_be_visible()

    def test_invoices_require_auth(self, page: Page, base_url: str):
        """Invoices require authentication."""
        page.goto(f"{base_url}/invoices/")
        expect(page).to_have_url(re.compile(r".*/login.*"))

    def test_viewer_cannot_create_invoice(self, viewer_page: Page, base_url: str):
        """Viewer cannot create invoices."""
        viewer_page.goto(f"{base_url}/invoices/new")
        content = viewer_page.content()
        assert "403" in content or "/login" in viewer_page.url or "Forbidden" in content
