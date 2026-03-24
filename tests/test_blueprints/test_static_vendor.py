"""Smoke tests for vendored static assets."""

import pytest

pytestmark = pytest.mark.blueprint


@pytest.mark.smoke
class TestVendoredAssets:
    """Verify vendored frontend libraries are served correctly."""

    def test_bootstrap_css(self, client):
        """Bootstrap CSS is served from vendor directory."""
        resp = client.get("/static/vendor/bootstrap.min.css")
        assert resp.status_code == 200

    def test_htmx_js(self, client):
        """HTMX JS is served from vendor directory."""
        resp = client.get("/static/vendor/htmx.min.js")
        assert resp.status_code == 200

    def test_alpine_js(self, client):
        """Alpine.js is served from vendor directory."""
        resp = client.get("/static/vendor/cdn.min.js")
        assert resp.status_code == 200

    def test_bootstrap_bundle_js(self, client):
        """Bootstrap JS bundle is served from vendor directory."""
        resp = client.get("/static/vendor/bootstrap.bundle.min.js")
        assert resp.status_code == 200

    def test_bootstrap_icons_css(self, client):
        """Bootstrap Icons CSS is served from vendor directory."""
        resp = client.get("/static/vendor/bootstrap-icons.min.css")
        assert resp.status_code == 200

    def test_bootstrap_icons_woff2(self, client):
        """Bootstrap Icons woff2 font file is served."""
        resp = client.get("/static/vendor/fonts/bootstrap-icons.woff2")
        assert resp.status_code == 200
