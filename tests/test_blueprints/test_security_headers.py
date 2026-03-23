"""Tests for security response headers, session cookie config, and rate limiting."""

import pytest


class TestSecurityHeaders:
    """Verify security headers are present on all responses."""

    def test_x_frame_options_present(self, client):
        """X-Frame-Options header is set to SAMEORIGIN."""
        response = client.get("/login")
        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_x_content_type_options_present(self, client):
        """X-Content-Type-Options header is set to nosniff globally."""
        response = client.get("/login")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_csp_header_present(self, client):
        """Content-Security-Policy header is present and includes default-src."""
        response = client.get("/login")
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "script-src" in csp
        assert "style-src" in csp

    def test_referrer_policy_present(self, client):
        """Referrer-Policy header is set."""
        response = client.get("/login")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_hsts_not_set_in_testing(self, client):
        """HSTS header is NOT set when TESTING is True (or DEBUG is True)."""
        response = client.get("/login")
        assert "Strict-Transport-Security" not in response.headers

    def test_headers_on_error_pages(self, client):
        """Security headers are present even on 404 error responses."""
        response = client.get("/nonexistent-page-12345")
        assert response.status_code == 404
        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_headers_on_authenticated_pages(self, logged_in_client):
        """Security headers are present on authenticated page responses."""
        response = logged_in_client.get("/dashboard")
        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert response.headers.get("Content-Security-Policy") is not None


class TestRateLimiter:
    """Verify rate limiter is initialized."""

    def test_limiter_in_extensions(self, app):
        """Flask-Limiter is initialized as an app extension."""
        assert "limiter" in app.extensions

    def test_limiter_importable(self):
        """Limiter can be imported from app.extensions for use in blueprints."""
        from app.extensions import limiter
        assert limiter is not None


class TestSessionCookieConfig:
    """Verify session cookie settings in ProductionConfig."""

    def test_production_session_cookie_secure(self):
        """ProductionConfig sets SESSION_COOKIE_SECURE to True."""
        from app.config import ProductionConfig
        assert ProductionConfig.SESSION_COOKIE_SECURE is True

    def test_production_session_cookie_httponly(self):
        """ProductionConfig sets SESSION_COOKIE_HTTPONLY to True."""
        from app.config import ProductionConfig
        assert ProductionConfig.SESSION_COOKIE_HTTPONLY is True

    def test_production_session_cookie_samesite(self):
        """ProductionConfig sets SESSION_COOKIE_SAMESITE to Lax."""
        from app.config import ProductionConfig
        assert ProductionConfig.SESSION_COOKIE_SAMESITE == "Lax"

    def test_testing_config_no_cookie_secure(self):
        """TestingConfig does not force SESSION_COOKIE_SECURE (inherits default)."""
        from app.config import TestingConfig
        # TestingConfig should not have SECURE set (would break test client)
        assert not getattr(TestingConfig, "SESSION_COOKIE_SECURE", False)
