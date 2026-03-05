"""Blueprint tests for authentication routes.

Flask-Security handles /login, /logout, /change automatically.
The app's auth_bp only adds the / root redirect.
"""

import pytest
from flask_security import hash_password


pytestmark = pytest.mark.blueprint


def test_root_redirects_to_login_when_anon(client):
    """Anonymous GET / redirects to the login page."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.location


def test_root_redirects_to_dashboard_when_logged_in(logged_in_client):
    """Authenticated GET / redirects to /dashboard."""
    response = logged_in_client.get("/")
    assert response.status_code == 302
    assert "/dashboard" in response.location


def test_login_page_renders(client):
    """GET /login returns 200 with a rendered login page."""
    response = client.get("/login")
    assert response.status_code == 200
    # Flask-Security's login template should contain a password field
    assert b"password" in response.data.lower()


def test_login_success(app, db_session, client):
    """POST /login with valid credentials redirects to /dashboard."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        user_datastore.create_user(
            username="logintest",
            email="logintest@example.com",
            password=hash_password("correctpass"),
            first_name="Login",
            last_name="Test",
        )
        db_session.commit()

    response = client.post(
        "/login",
        data={"email": "logintest@example.com", "password": "correctpass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/dashboard" in response.location


def test_login_failure(app, db_session, client):
    """POST /login with wrong password stays on login page, not dashboard."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        user_datastore.create_user(
            username="failtest",
            email="failtest@example.com",
            password=hash_password("correctpass"),
            first_name="Fail",
            last_name="Test",
        )
        db_session.commit()

    # Use follow_redirects=False to check the raw response
    response = client.post(
        "/login",
        data={"email": "failtest@example.com", "password": "wrongpass"},
        follow_redirects=False,
    )
    # Flask-Security returns 200 (re-renders login form) on failed login,
    # NOT a 302 redirect to dashboard
    assert response.status_code == 200
    # The response must NOT redirect to dashboard
    assert response.location is None or "/dashboard" not in response.location
    # The login form should still be present (password field visible)
    assert b"password" in response.data.lower()


def test_login_failure_nonexistent_user(client):
    """POST /login with a non-existent email stays on login page."""
    response = client.post(
        "/login",
        data={"email": "nobody@example.com", "password": "anything"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.location is None or "/dashboard" not in response.location


def test_logout(logged_in_client):
    """Authenticated GET /logout redirects to the login page."""
    response = logged_in_client.get("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


def test_logout_actually_deauthenticates(logged_in_client):
    """After logout, accessing /dashboard/ requires re-authentication."""
    # Logout
    logged_in_client.get("/logout", follow_redirects=True)
    # Now try to access a protected page
    response = logged_in_client.get("/dashboard/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location
