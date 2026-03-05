"""Blueprint tests for export routes.

Tests CSV and XLSX export endpoints for customers, inventory, orders,
and invoices.  Verifies correct MIME types, status codes, and
unsupported format handling.
"""

import pytest

pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    """Anonymous users are redirected to the login page."""

    def test_export_customers_csv_unauthenticated(self, client):
        response = client.get("/export/customers/csv")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_export_customers_xlsx_unauthenticated(self, client):
        response = client.get("/export/customers/xlsx")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_export_orders_unauthenticated(self, client):
        response = client.get("/export/orders/csv")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_export_invoices_unauthenticated(self, client):
        response = client.get("/export/invoices/csv")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_export_inventory_unauthenticated(self, client):
        response = client.get("/export/inventory/csv")
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------


class TestCsvExports:
    """Authenticated users can export data to CSV."""

    def test_export_customers_csv(self, logged_in_client, app, db_session):
        """GET /export/customers/csv returns 200 with text/csv content type."""
        response = logged_in_client.get("/export/customers/csv")
        assert response.status_code == 200
        assert "text/csv" in response.content_type

    def test_export_orders_csv(self, logged_in_client, app, db_session):
        """GET /export/orders/csv returns 200 with text/csv content type."""
        response = logged_in_client.get("/export/orders/csv")
        assert response.status_code == 200
        assert "text/csv" in response.content_type

    def test_export_invoices_csv(self, logged_in_client, app, db_session):
        """GET /export/invoices/csv returns 200 with text/csv content type."""
        response = logged_in_client.get("/export/invoices/csv")
        assert response.status_code == 200
        assert "text/csv" in response.content_type

    def test_export_inventory_csv(self, logged_in_client, app, db_session):
        """GET /export/inventory/csv returns 200 with text/csv content type."""
        response = logged_in_client.get("/export/inventory/csv")
        assert response.status_code == 200
        assert "text/csv" in response.content_type


# ---------------------------------------------------------------------------
# XLSX exports
# ---------------------------------------------------------------------------


class TestXlsxExports:
    """Authenticated users can export data to XLSX."""

    def test_export_customers_xlsx(self, logged_in_client, app, db_session):
        """GET /export/customers/xlsx returns 200 with spreadsheet MIME type."""
        response = logged_in_client.get("/export/customers/xlsx")
        assert response.status_code == 200
        assert "spreadsheetml" in response.content_type

    def test_export_orders_xlsx(self, logged_in_client, app, db_session):
        """GET /export/orders/xlsx returns 200 with spreadsheet MIME type."""
        response = logged_in_client.get("/export/orders/xlsx")
        assert response.status_code == 200
        assert "spreadsheetml" in response.content_type

    def test_export_invoices_xlsx(self, logged_in_client, app, db_session):
        """GET /export/invoices/xlsx returns 200 with spreadsheet MIME type."""
        response = logged_in_client.get("/export/invoices/xlsx")
        assert response.status_code == 200
        assert "spreadsheetml" in response.content_type

    def test_export_inventory_xlsx(self, logged_in_client, app, db_session):
        """GET /export/inventory/xlsx returns 200 with spreadsheet MIME type."""
        response = logged_in_client.get("/export/inventory/xlsx")
        assert response.status_code == 200
        assert "spreadsheetml" in response.content_type


# ---------------------------------------------------------------------------
# Unsupported format
# ---------------------------------------------------------------------------


class TestUnsupportedFormat:
    """Unsupported export formats return 400."""

    def test_export_unsupported_format(self, logged_in_client, app, db_session):
        """GET /export/customers/pdf returns 400."""
        response = logged_in_client.get("/export/customers/pdf")
        assert response.status_code == 400
