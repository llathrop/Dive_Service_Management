"""Tests for export blueprint role restrictions.

Verifies that viewer-role users are denied access (403) while admin
and technician users can access all export routes.
"""

import pytest

EXPORT_ROUTES = [
    "/export/customers/csv",
    "/export/inventory/csv",
    "/export/orders/csv",
    "/export/invoices/csv",
]


class TestExportViewerDenied:
    """Viewer role must get 403 on all export routes."""

    @pytest.mark.parametrize("url", EXPORT_ROUTES)
    def test_viewer_gets_403(self, viewer_client, url):
        resp = viewer_client.get(url)
        assert resp.status_code == 403


class TestExportAdminAllowed:
    """Admin role must be able to access export routes."""

    @pytest.mark.parametrize("url", EXPORT_ROUTES)
    def test_admin_can_access(self, admin_client, url):
        resp = admin_client.get(url)
        assert resp.status_code == 200


class TestExportTechnicianAllowed:
    """Technician role must be able to access export routes."""

    @pytest.mark.parametrize("url", EXPORT_ROUTES)
    def test_technician_can_access(self, logged_in_client, url):
        resp = logged_in_client.get(url)
        assert resp.status_code == 200
