"""Shared pytest fixtures for the Dive Service Management test suite.

Provides app, client, db_session, runner, auth_user, admin_user,
and logged_in_client fixtures used across all test modules.
"""

import pytest
from flask_security import hash_password

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db


@pytest.fixture()
def app():
    """Create the Flask application with TestingConfig.

    Each test gets a fresh app with clean tables.
    """
    app = create_app(TestingConfig)

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db_session(app):
    """Provide a database session for the test.

    Yields db.session within the app context, and rolls back
    after the test for cleanup.
    """
    with app.app_context():
        yield _db.session
        _db.session.rollback()


@pytest.fixture()
def client(app):
    """Provide a Flask test client."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """Provide a Flask CLI test runner."""
    return app.test_cli_runner()


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


@pytest.fixture()
def admin_user(app, db_session):
    """Create and return a user with the 'admin' role."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        admin_role = user_datastore.find_or_create_role(
            name="admin", description="Full system access"
        )
        user = user_datastore.create_user(
            username="adminuser",
            email="admin@example.com",
            password=hash_password("password"),
            first_name="Admin",
            last_name="User",
        )
        user_datastore.add_role_to_user(user, admin_role)
        db_session.commit()
        return user


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


@pytest.fixture()
def logged_in_client(app, db_session):
    """Create a user, log them in via the test client, and yield the client.

    The user has the 'technician' role. The client maintains the session
    cookie so subsequent requests are authenticated.
    """
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        tech_role = user_datastore.find_or_create_role(
            name="technician", description="Create/edit data, manage orders"
        )
        user = user_datastore.create_user(
            username="loggedinuser",
            email="loggedin@example.com",
            password=hash_password("password"),
            first_name="Logged",
            last_name="In",
        )
        user_datastore.add_role_to_user(user, tech_role)
        db_session.commit()

    client = _login_client(app, "loggedin@example.com", "password")
    with client:
        yield client


@pytest.fixture()
def admin_client(app, db_session):
    """Create an admin user, log them in, and yield the authenticated client."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        admin_role = user_datastore.find_or_create_role(
            name="admin", description="Full system access"
        )
        user = user_datastore.create_user(
            username="adminclient",
            email="adminclient@example.com",
            password=hash_password("password"),
            first_name="Admin",
            last_name="Client",
        )
        user_datastore.add_role_to_user(user, admin_role)
        db_session.commit()

    client = _login_client(app, "adminclient@example.com", "password")
    with client:
        yield client


@pytest.fixture()
def viewer_client(app, db_session):
    """Create a viewer user, log them in, and yield the authenticated client."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        viewer_role = user_datastore.find_or_create_role(
            name="viewer", description="Read-only access"
        )
        user = user_datastore.create_user(
            username="viewerclient",
            email="viewer@example.com",
            password=hash_password("password"),
            first_name="Viewer",
            last_name="Client",
        )
        user_datastore.add_role_to_user(user, viewer_role)
        db_session.commit()

    client = _login_client(app, "viewer@example.com", "password")
    with client:
        yield client
