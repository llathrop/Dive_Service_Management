"""UAT: Authentication and authorization.

Covers: login page rendering, successful login, failed login,
logout, dashboard access, role-based redirects.

Phase: 1 (Foundation)
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


def test_login_page_renders(page: Page, base_url: str):
    """Login page loads and shows email/password fields."""
    page.goto(f"{base_url}/login")
    expect(page.locator('input[name="email"]')).to_be_visible()
    expect(page.locator('input[name="password"]')).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_be_visible()


def test_login_success_redirects_to_dashboard(page: Page, base_url: str):
    """Valid credentials redirect to the dashboard."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="email"]', "admin@example.com")
    page.fill('input[name="password"]', "admin123")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    assert "/dashboard" in page.url


def test_login_failure_stays_on_login(page: Page, base_url: str):
    """Invalid credentials keep user on login page."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="email"]', "admin@example.com")
    page.fill('input[name="password"]', "wrongpassword")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url or "/dashboard" not in page.url


def test_dashboard_requires_auth(page: Page, base_url: str):
    """Anonymous access to /dashboard redirects to login."""
    page.goto(f"{base_url}/dashboard/")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url


def test_logout_deauthenticates(admin_page: Page, base_url: str):
    """After logout, user is redirected and cannot access dashboard."""
    admin_page.goto(f"{base_url}/logout")
    admin_page.wait_for_load_state("networkidle")
    assert "/login" in admin_page.url
    # Verify dashboard is no longer accessible
    admin_page.goto(f"{base_url}/dashboard/")
    admin_page.wait_for_load_state("networkidle")
    assert "/login" in admin_page.url


def test_health_endpoint(page: Page, base_url: str):
    """Health endpoint returns 200 (no auth required)."""
    response = page.goto(f"{base_url}/health")
    assert response.status == 200
