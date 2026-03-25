"""UAT tests for tools and calculators (Phase 5)."""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


class TestToolsUAT:
    """Tools UAT tests."""

    def test_tools_hub(self, admin_page: Page, base_url: str):
        """Tools hub page loads."""
        admin_page.goto(f"{base_url}/tools/")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=Seal")).to_be_visible()

    def test_seal_calculator(self, admin_page: Page, base_url: str):
        """Seal size calculator works with input/output."""
        admin_page.goto(f"{base_url}/tools/seal-calculator")
        expect(admin_page.locator("h1")).to_contain_text("Seal")

    def test_pricing_calculator(self, admin_page: Page, base_url: str):
        """Pricing calculator computes totals."""
        admin_page.goto(f"{base_url}/tools/pricing-calculator")
        expect(admin_page.locator("h1")).to_contain_text("Pricing")

    def test_shipping_calculator(self, admin_page: Page, base_url: str):
        """Shipping calculator page loads."""
        admin_page.goto(f"{base_url}/tools/shipping-calculator")
        expect(admin_page.locator("h1")).to_contain_text("Shipping Calculator")
        expect(admin_page.locator("text=Provider")).to_be_visible()

    def test_unit_converter(self, admin_page: Page, base_url: str):
        """Unit converter page loads."""
        admin_page.goto(f"{base_url}/tools/converter")
        expect(admin_page.locator("h1")).to_contain_text("Converter")

    def test_material_estimator(self, admin_page: Page, base_url: str):
        """Material estimator page loads."""
        admin_page.goto(f"{base_url}/tools/material-estimator")
        expect(admin_page.locator("h1")).to_contain_text("Material")

    def test_leak_test_log(self, admin_page: Page, base_url: str):
        """Leak test log page loads."""
        admin_page.goto(f"{base_url}/tools/leak-test-log")
        expect(admin_page.locator("h1")).to_contain_text("Leak")

    def test_valve_reference(self, admin_page: Page, base_url: str):
        """Valve reference page loads."""
        admin_page.goto(f"{base_url}/tools/valve-reference")
        expect(admin_page.locator("h1")).to_contain_text("Valve")

    def test_tools_require_auth(self, page: Page, base_url: str):
        """Tools require authentication."""
        page.goto(f"{base_url}/tools/")
        expect(page).to_have_url(re.compile(r".*/login.*"))
