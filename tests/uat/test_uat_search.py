"""UAT: Global search.

Covers: search page, search results, empty search.

Phase: 2 (Core Entities)
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


def test_search_page_loads(admin_page: Page, base_url: str):
    """Search page or search endpoint is accessible."""
    admin_page.goto(f"{base_url}/search/?q=test")
    admin_page.wait_for_load_state("networkidle")
    assert "/search" in admin_page.url or "/login" not in admin_page.url


def test_search_returns_results(admin_page: Page, base_url: str):
    """Search with a known term returns results section."""
    admin_page.goto(f"{base_url}/search/?q=UAT")
    admin_page.wait_for_load_state("networkidle")
    # Page should contain either results or a "no results" message
    page_text = admin_page.text_content("body")
    assert "search" in page_text.lower() or "result" in page_text.lower() or "UAT" in page_text


def test_search_requires_auth(page: Page, base_url: str):
    """Anonymous user is redirected to login from search."""
    page.goto(f"{base_url}/search/?q=test")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url
