"""Blueprint tests for report routes.

Tests the reports hub and individual report endpoints, verifying
authenticated access returns 200 and unauthenticated access redirects
to login.
"""

import pytest

pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    """Anonymous users are redirected to the login page."""

    def test_hub_unauthenticated_redirects(self, client):
        response = client.get("/reports/")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_revenue_unauthenticated_redirects(self, client):
        response = client.get("/reports/revenue")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_orders_unauthenticated_redirects(self, client):
        response = client.get("/reports/orders")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_inventory_unauthenticated_redirects(self, client):
        response = client.get("/reports/inventory")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_customers_unauthenticated_redirects(self, client):
        response = client.get("/reports/customers")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_aging_unauthenticated_redirects(self, client):
        response = client.get("/reports/aging")
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Authenticated access
# ---------------------------------------------------------------------------


class TestAuthenticatedAccess:
    """Authenticated users can access all report endpoints."""

    def test_hub_authenticated(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/reports/")
        assert response.status_code == 200

    def test_revenue_report(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/reports/revenue")
        assert response.status_code == 200

    def test_orders_report(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/reports/orders")
        assert response.status_code == 200

    def test_inventory_report(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/reports/inventory")
        assert response.status_code == 200

    def test_customers_report(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/reports/customers")
        assert response.status_code == 200

    def test_aging_report(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/reports/aging")
        assert response.status_code == 200

    def test_revenue_with_date_filter(self, logged_in_client, app, db_session):
        """Revenue report with date filter parameters returns 200."""
        response = logged_in_client.get(
            "/reports/revenue?date_from=2026-01-01&date_to=2026-03-31"
        )
        assert response.status_code == 200
