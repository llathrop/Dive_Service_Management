"""UAT test fixtures for Playwright browser testing.

Provides fixtures for connecting to the live Flask app running in Docker
and performing browser-based user acceptance tests.
"""

import os

import pytest
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("DSM_UAT_BASE_URL", "http://localhost:8081")

# Default credentials (seeded by flask create-admin or seed-db)
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"
TECH_EMAIL = "tech@example.com"
TECH_PASSWORD = "tech123"
VIEWER_EMAIL = "viewer@example.com"
VIEWER_PASSWORD = "viewer123"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url():
    """Base URL of the live Flask application."""
    return BASE_URL


@pytest.fixture(scope="session")
def browser_context_args():
    """Default browser context arguments for all tests."""
    return {
        "ignore_https_errors": True,
        "viewport": {"width": 1280, "height": 720},
    }


def _login(page: Page, base_url: str, email: str, password: str):
    """Helper: navigate to login page and authenticate."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    # Wait for redirect to dashboard or page load
    page.wait_for_load_state("networkidle")


@pytest.fixture
def live_url(base_url):
    """Alias for base_url for clarity in tests."""
    return base_url


@pytest.fixture
def admin_page(page: Page, base_url: str):
    """A Playwright page logged in as admin."""
    _login(page, base_url, ADMIN_EMAIL, ADMIN_PASSWORD)
    return page


@pytest.fixture
def tech_page(page: Page, base_url: str):
    """A Playwright page logged in as technician."""
    _login(page, base_url, TECH_EMAIL, TECH_PASSWORD)
    return page


@pytest.fixture
def viewer_page(page: Page, base_url: str):
    """A Playwright page logged in as viewer (read-only)."""
    _login(page, base_url, VIEWER_EMAIL, VIEWER_PASSWORD)
    return page
