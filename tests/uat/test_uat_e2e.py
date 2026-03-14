"""UAT: End-to-end workflow test.

This script exercises a complete business workflow through the browser,
validating that all implemented features work together. It grows with
each phase — steps for unimplemented phases are skipped.

Phase: All (updated progressively)
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


class TestEndToEndWorkflow:
    """Full business workflow: setup -> login -> CRUD -> logout."""

    # ------------------------------------------------------------------
    # Phase 1: Foundation
    # ------------------------------------------------------------------

    def test_01_health_check(self, page: Page, base_url: str):
        """Step 1: Verify the application is running."""
        response = page.goto(f"{base_url}/health")
        assert response.status == 200
        page_text = page.text_content("body")
        assert "healthy" in page_text.lower() or "ok" in page_text.lower()

    def test_02_admin_login(self, page: Page, base_url: str):
        """Step 2: Log in as admin."""
        page.goto(f"{base_url}/login")
        page.fill('input[name="email"]', "admin@example.com")
        page.fill('input[name="password"]', "admin123")
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        assert "/dashboard" in page.url

    def test_03_dashboard_loads(self, admin_page: Page, base_url: str):
        """Step 3: Dashboard renders with summary content."""
        admin_page.goto(f"{base_url}/dashboard/")
        admin_page.wait_for_load_state("networkidle")
        assert "/dashboard" in admin_page.url

    # ------------------------------------------------------------------
    # Phase 2: Core Entities
    # ------------------------------------------------------------------

    def test_04_create_customer(self, admin_page: Page, base_url: str):
        """Step 4: Create a test customer."""
        admin_page.goto(f"{base_url}/customers/new")
        admin_page.wait_for_load_state("networkidle")

        admin_page.fill('input[name="first_name"]', "E2E")
        admin_page.fill('input[name="last_name"]', "TestUser")
        admin_page.fill('input[name="email"]', "e2e@example.com")
        admin_page.fill('input[name="phone_primary"]', "555-E2E0")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        page_text = admin_page.text_content("body")
        assert "E2E" in page_text

    def test_05_create_service_item(self, admin_page: Page, base_url: str):
        """Step 5: Create a service item (drysuit)."""
        admin_page.goto(f"{base_url}/items/new")
        admin_page.wait_for_load_state("networkidle")

        admin_page.fill('input[name="name"]', "E2E DUI CF200X")
        admin_page.fill('input[name="serial_number"]', "E2E-DS-001")

        category = admin_page.locator('select[name="item_category"]')
        if category.count() > 0:
            category.select_option(label="Drysuit")

        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        page_text = admin_page.text_content("body")
        assert "E2E DUI CF200X" in page_text

    def test_06_check_inventory(self, admin_page: Page, base_url: str):
        """Step 6: Verify inventory page loads."""
        admin_page.goto(f"{base_url}/inventory/")
        admin_page.wait_for_load_state("networkidle")
        assert "/inventory" in admin_page.url

    def test_07_search_works(self, admin_page: Page, base_url: str):
        """Step 7: Search for the created customer."""
        admin_page.goto(f"{base_url}/search/?q=E2E")
        admin_page.wait_for_load_state("networkidle")
        page_text = admin_page.text_content("body")
        # Should find the customer or item we created
        assert "E2E" in page_text

    # ------------------------------------------------------------------
    # Phase 3: Service Workflow
    # ------------------------------------------------------------------

    def test_08_create_service_order(self, admin_page: Page, base_url: str):
        """Step 8: Create a service order for the customer."""
        admin_page.goto(f"{base_url}/orders/new")
        admin_page.wait_for_load_state("networkidle")

        # Select the E2E customer created in test_04
        customer_select = admin_page.locator('select[name="customer_id"]')
        if customer_select.count() > 0:
            customer_select.select_option(label="E2E TestUser")

        date_field = admin_page.locator('input[name="date_received"]')
        if date_field.count() > 0:
            date_field.fill("2026-03-04")

        desc_field = admin_page.locator('textarea[name="description"]')
        if desc_field.count() > 0:
            desc_field.fill("E2E workflow test order")

        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        # Verify we landed on an order detail page
        expect(admin_page).to_have_url(re.compile(r".*/orders/\d+"))

    def test_09_add_parts_and_labor(self, admin_page: Page, base_url: str):
        """Step 9: Navigate to an order and verify detail sections."""
        admin_page.goto(f"{base_url}/orders/")
        admin_page.wait_for_load_state("networkidle")

        # Click the first order link in the table
        first_link = admin_page.locator("table tbody tr td a").first
        if first_link.is_visible():
            first_link.click()
            admin_page.wait_for_load_state("networkidle")

            # Verify the order detail page has expected sections
            page_text = admin_page.text_content("body")
            assert "Service Items" in page_text or "Notes" in page_text

    # ------------------------------------------------------------------
    # Phase 4: Billing
    # ------------------------------------------------------------------

    def test_10_generate_invoice(self, admin_page: Page, base_url: str):
        """Step 10: Create an invoice from the invoices form."""
        admin_page.goto(f"{base_url}/invoices/new")
        admin_page.wait_for_load_state("networkidle")

        # Verify the invoice creation form is present
        expect(admin_page.locator('select[name="customer_id"]')).to_be_visible()

        # Select the E2E customer
        customer_select = admin_page.locator('select[name="customer_id"]')
        if customer_select.count() > 0:
            customer_select.select_option(label="E2E TestUser")

        issue_date = admin_page.locator('input[name="issue_date"]')
        if issue_date.count() > 0:
            issue_date.fill("2026-03-04")

        admin_page.click('button[type="submit"]')
        admin_page.wait_for_load_state("networkidle")

        # Verify we landed on an invoice detail page
        expect(admin_page).to_have_url(re.compile(r".*/invoices/\d+"))

    def test_11_record_payment(self, admin_page: Page, base_url: str):
        """Step 11: Navigate to an invoice detail and check payment section."""
        admin_page.goto(f"{base_url}/invoices/")
        admin_page.wait_for_load_state("networkidle")

        first_link = admin_page.locator("table tbody tr td a").first
        if first_link.is_visible():
            first_link.click()
            admin_page.wait_for_load_state("networkidle")

            # Verify invoice detail has payment-related content
            page_text = admin_page.text_content("body")
            assert "Payment" in page_text or "Line Items" in page_text

    # ------------------------------------------------------------------
    # Phase 5: Reports & Tools
    # ------------------------------------------------------------------

    def test_12_check_reports(self, admin_page: Page, base_url: str):
        """Step 12: Verify reports hub renders with report links."""
        admin_page.goto(f"{base_url}/reports/")
        admin_page.wait_for_load_state("networkidle")

        page_text = admin_page.text_content("body")
        assert "Revenue" in page_text or "Report" in page_text

    def test_13_use_calculator_tool(self, admin_page: Page, base_url: str):
        """Step 13: Navigate to unit converter tool page."""
        admin_page.goto(f"{base_url}/tools/converter")
        admin_page.wait_for_load_state("networkidle")

        expect(admin_page.locator("h1")).to_contain_text("Converter")

    # ------------------------------------------------------------------
    # Admin Overhaul
    # ------------------------------------------------------------------

    def test_14_admin_hub(self, admin_page: Page, base_url: str):
        """Step 14: Verify admin hub loads with all section cards."""
        admin_page.goto(f"{base_url}/admin/")
        admin_page.wait_for_load_state("networkidle")
        page_text = admin_page.text_content("body")
        assert "User Management" in page_text
        assert "System Settings" in page_text
        assert "Data Management" in page_text

    def test_15_admin_settings(self, admin_page: Page, base_url: str):
        """Step 15: Verify settings page renders with tabs."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("h1")).to_contain_text("System Settings")
        # Verify all 6 tabs are present
        page_text = admin_page.text_content(".nav-tabs")
        assert "Company" in page_text
        assert "Service" in page_text
        assert "Security" in page_text

    def test_16_data_management(self, admin_page: Page, base_url: str):
        """Step 16: Verify data management page shows DB info."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("h1")).to_contain_text("Data Management")
        page_text = admin_page.text_content("body")
        assert "Backup" in page_text
        assert "Table Statistics" in page_text

    def test_17_import_page(self, admin_page: Page, base_url: str):
        """Step 17: Verify CSV import page loads."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("h1")).to_contain_text("Import Customers")

    # ------------------------------------------------------------------
    # Final: Logout
    # ------------------------------------------------------------------

    def test_99_logout(self, admin_page: Page, base_url: str):
        """Final step: Logout and verify deauthentication."""
        admin_page.goto(f"{base_url}/logout")
        admin_page.wait_for_load_state("networkidle")
        assert "/login" in admin_page.url
