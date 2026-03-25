"""Smoke tests for the authenticated core application surfaces."""

import pytest


pytestmark = pytest.mark.smoke

CORE_ROUTES = (
    "/dashboard/",
    "/customers/",
    "/items/",
    "/inventory/",
    "/price-list/",
    "/orders/",
    "/reports/",
    "/tools/",
    "/notifications/",
    "/admin/",
)


@pytest.mark.parametrize("url", CORE_ROUTES)
def test_core_routes_render_for_admin(admin_client, url):
    """The main internal pages render for an authenticated admin user."""
    response = admin_client.get(url)
    assert response.status_code == 200
