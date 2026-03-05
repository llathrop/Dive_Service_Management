"""Smoke tests: verify key pages load and return expected status codes."""

import pytest


pytestmark = pytest.mark.smoke


def test_login_page_loads(client):
    """GET /login returns 200 OK."""
    response = client.get("/login")
    assert response.status_code == 200


def test_root_redirects(client):
    """GET / returns a 302 redirect (to login or dashboard)."""
    response = client.get("/")
    assert response.status_code == 302


def test_dashboard_requires_login(client):
    """GET /dashboard/ without login returns a redirect (302)."""
    response = client.get("/dashboard/")
    assert response.status_code == 302


def test_404_page(client):
    """GET a nonexistent URL returns 404 and contains '404' in the body."""
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert b"404" in response.data


def test_static_css_loads(client):
    """GET the main stylesheet returns 200 OK."""
    response = client.get("/static/css/style.css")
    assert response.status_code == 200


def test_static_js_loads(client):
    """GET the main JavaScript file returns 200 OK."""
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
