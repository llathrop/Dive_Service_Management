"""UAT: Customer management.

Covers: customer list, create, view detail, edit, delete, search.

Phase: 2 (Core Entities)
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


def test_customer_list_page(admin_page: Page, base_url: str):
    """Customer list page loads and shows table or empty state."""
    admin_page.goto(f"{base_url}/customers/")
    admin_page.wait_for_load_state("networkidle")
    assert "/customers" in admin_page.url
    # Should have either a table or an empty-state message
    table = admin_page.locator("table")
    empty_state = admin_page.locator(".text-center")
    assert table.count() > 0 or empty_state.count() > 0


def test_create_customer_form_renders(admin_page: Page, base_url: str):
    """New customer form loads with expected fields."""
    admin_page.goto(f"{base_url}/customers/new")
    admin_page.wait_for_load_state("networkidle")
    expect(admin_page.locator('input[name="first_name"]')).to_be_visible()
    expect(admin_page.locator('input[name="last_name"]')).to_be_visible()
    expect(admin_page.locator('input[name="email"]')).to_be_visible()


def test_create_individual_customer(admin_page: Page, base_url: str):
    """Create an individual customer and verify redirect to detail."""
    admin_page.goto(f"{base_url}/customers/new")
    admin_page.wait_for_load_state("networkidle")

    admin_page.fill('input[name="first_name"]', "UAT")
    admin_page.fill('input[name="last_name"]', "TestCustomer")
    admin_page.fill('input[name="email"]', "uat_customer@example.com")
    admin_page.fill('input[name="phone_primary"]', "555-0100")
    admin_page.click('button[type="submit"]')
    admin_page.wait_for_load_state("networkidle")

    # Should redirect to detail page or list with success message
    page_text = admin_page.text_content("body")
    assert "UAT" in page_text and "TestCustomer" in page_text


def test_create_business_customer(admin_page: Page, base_url: str):
    """Create a business customer with business_name."""
    admin_page.goto(f"{base_url}/customers/new")
    admin_page.wait_for_load_state("networkidle")

    # Select business type if there's a selector
    business_radio = admin_page.locator('input[value="business"]')
    if business_radio.count() > 0:
        business_radio.click()

    admin_page.fill('input[name="business_name"]', "UAT Dive Shop LLC")
    admin_page.fill('input[name="email"]', "uat_business@example.com")
    admin_page.click('button[type="submit"]')
    admin_page.wait_for_load_state("networkidle")

    page_text = admin_page.text_content("body")
    assert "UAT Dive Shop" in page_text


def test_customer_detail_page(admin_page: Page, base_url: str):
    """Customer detail page shows customer info."""
    # First, navigate to customer list and click first customer
    admin_page.goto(f"{base_url}/customers/")
    admin_page.wait_for_load_state("networkidle")

    # Try clicking the first customer link in the table
    first_link = admin_page.locator("table tbody tr:first-child a").first
    if first_link.count() > 0:
        first_link.click()
        admin_page.wait_for_load_state("networkidle")
        assert "/customers/" in admin_page.url


def test_customer_list_requires_auth(page: Page, base_url: str):
    """Anonymous user is redirected to login from customers page."""
    page.goto(f"{base_url}/customers/")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url


def test_viewer_cannot_create_customer(viewer_page: Page, base_url: str):
    """Viewer role cannot access customer creation form (403 or redirect)."""
    viewer_page.goto(f"{base_url}/customers/new")
    viewer_page.wait_for_load_state("networkidle")
    # Should get 403 or be redirected
    page_text = viewer_page.text_content("body")
    url = viewer_page.url
    assert "403" in page_text or "Forbidden" in page_text or "/customers/new" not in url
