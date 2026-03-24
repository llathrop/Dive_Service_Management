"""Shared fixture helpers for the Dive Service Management test suite.

Contains common fixture logic used by both the main conftest.py and the
MariaDB conftest.py to avoid duplication.
"""

import pytest
from flask_security import hash_password

from app.extensions import db as _db


def make_db_session_fixture():
    """Return a db_session fixture function."""

    @pytest.fixture()
    def db_session(app):
        """Provide a database session for the test.

        Yields db.session within the app context, and rolls back
        after the test for cleanup.
        """
        with app.app_context():
            yield _db.session
            _db.session.rollback()

    return db_session


def make_client_fixture():
    """Return a client fixture function."""

    @pytest.fixture()
    def client(app):
        """Provide a Flask test client."""
        return app.test_client()

    return client


def make_auth_user_fixture():
    """Return an auth_user fixture function."""

    @pytest.fixture()
    def auth_user(app, db_session):
        """Create and return a user with the 'technician' role."""
        with app.app_context():
            user_datastore = app.extensions["security"].datastore
            tech_role = user_datastore.find_or_create_role(
                name="technician", description="Create/edit data, manage orders"
            )
            user = user_datastore.create_user(
                username="techuser",
                email="tech@example.com",
                password=hash_password("password"),
                first_name="Tech",
                last_name="User",
            )
            user_datastore.add_role_to_user(user, tech_role)
            db_session.commit()
            return user

    return auth_user


def _login_client(app, email, password):
    """Create a test client and log in, verifying authentication succeeded.

    Raises AssertionError if the login POST does not result in a
    successful redirect to /dashboard (which proves the session is
    authenticated).
    """
    client = app.test_client()
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    # Flask-Security redirects to SECURITY_POST_LOGIN_VIEW (/dashboard) on success
    assert response.status_code == 302, (
        f"Login for {email} failed: expected 302, got {response.status_code}"
    )
    assert "/dashboard" in response.location, (
        f"Login for {email} did not redirect to dashboard: {response.location}"
    )
    return client
