"""Tests for the in-app documentation blueprint."""

import pytest

pytestmark = pytest.mark.blueprint


class TestDocsIndex:
    """Tests for GET /docs."""

    def test_docs_index_requires_auth(self, client):
        """Unauthenticated users are redirected to login."""
        resp = client.get("/docs/")
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "")

    def test_docs_index_renders(self, logged_in_client):
        """Authenticated users see the docs index page."""
        resp = logged_in_client.get("/docs/")
        assert resp.status_code == 200
        assert b"Documentation" in resp.data

    def test_docs_index_lists_documents(self, logged_in_client):
        """The index page lists available documentation files."""
        resp = logged_in_client.get("/docs/")
        assert resp.status_code == 200
        # Should contain links to at least the user guide
        assert b"user-guide" in resp.data


class TestDocsDetail:
    """Tests for GET /docs/<slug>."""

    def test_docs_detail_requires_auth(self, client):
        """Unauthenticated users are redirected to login."""
        resp = client.get("/docs/user-guide")
        assert resp.status_code == 302

    def test_docs_detail_renders_user_guide(self, logged_in_client):
        """The user guide renders as HTML."""
        resp = logged_in_client.get("/docs/user-guide")
        assert resp.status_code == 200
        assert b"User Guide" in resp.data or b"user guide" in resp.data.lower()

    def test_docs_detail_renders_architecture(self, logged_in_client):
        """The architecture doc renders as HTML."""
        resp = logged_in_client.get("/docs/architecture")
        assert resp.status_code == 200

    def test_docs_detail_404_for_unknown_slug(self, logged_in_client):
        """Unknown slugs return 404."""
        resp = logged_in_client.get("/docs/nonexistent-doc")
        assert resp.status_code == 404

    def test_docs_detail_has_sidebar_nav(self, logged_in_client):
        """The detail page includes a sidebar with doc navigation."""
        resp = logged_in_client.get("/docs/user-guide")
        assert resp.status_code == 200
        assert b"Documents" in resp.data

    def test_docs_detail_has_breadcrumb(self, logged_in_client):
        """The detail page includes a breadcrumb back to docs index."""
        resp = logged_in_client.get("/docs/configuration")
        assert resp.status_code == 200
        assert b"breadcrumb" in resp.data


class TestDocsNavLink:
    """Test that the docs link appears in the sidebar."""

    def test_sidebar_has_docs_link(self, logged_in_client):
        """The main sidebar includes a Documentation link."""
        resp = logged_in_client.get("/")
        assert resp.status_code in (200, 302)
        if resp.status_code == 200:
            assert b"Documentation" in resp.data
