"""Tests for reports blueprint role restrictions.

Verifies that viewer-role users are denied access (403) while admin
and technician users can access all report routes.
"""

import pytest

REPORT_ROUTES = [
    "/reports/",
    "/reports/revenue",
    "/reports/orders",
    "/reports/inventory",
    "/reports/customers",
    "/reports/aging",
]


class TestReportsViewerDenied:
    """Viewer role must get 403 on all report routes."""

    @pytest.mark.parametrize("url", REPORT_ROUTES)
    def test_viewer_gets_403(self, viewer_client, url):
        resp = viewer_client.get(url)
        assert resp.status_code == 403


class TestReportsAdminAllowed:
    """Admin role must be able to access report routes."""

    @pytest.mark.parametrize("url", REPORT_ROUTES)
    def test_admin_can_access(self, admin_client, url):
        resp = admin_client.get(url)
        assert resp.status_code == 200


class TestReportsTechnicianAllowed:
    """Technician role must be able to access report routes."""

    @pytest.mark.parametrize("url", REPORT_ROUTES)
    def test_technician_can_access(self, logged_in_client, url):
        resp = logged_in_client.get(url)
        assert resp.status_code == 200
