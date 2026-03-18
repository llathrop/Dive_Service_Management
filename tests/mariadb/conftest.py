"""Shared fixtures and configuration for MariaDB parity tests.

Skips the entire test directory when MariaDB is not reachable.  Uses
MariaDBTestingConfig so that tests run against a real MariaDB instance
instead of SQLite in-memory.
"""

import pytest
from flask_security import hash_password
from sqlalchemy import text

from app import create_app
from app.config import MariaDBTestingConfig
from app.extensions import db as _db


# ---------------------------------------------------------------------------
# Auto-apply the ``mariadb`` marker to every test in this directory
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(items):
    """Add the 'mariadb' marker to all tests collected from this package."""
    for item in items:
        if "mariadb" in str(item.fspath):
            item.add_marker(pytest.mark.mariadb)


# ---------------------------------------------------------------------------
# Skip entire directory if MariaDB is unreachable
# ---------------------------------------------------------------------------

def _mariadb_is_available():
    """Try to connect to MariaDB using MariaDBTestingConfig.

    Returns True if a connection succeeds, False otherwise.
    """
    try:
        app = create_app(MariaDBTestingConfig)
        with app.app_context():
            with _db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# Run the check once at collection time
_mariadb_available = None


def _check_mariadb():
    global _mariadb_available
    if _mariadb_available is None:
        _mariadb_available = _mariadb_is_available()
    return _mariadb_available


def pytest_configure(config):
    """Skip the entire mariadb package if the database is not reachable."""
    # This runs early enough that we can set a flag for the session fixture
    pass


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mariadb_available():
    """Session-scoped check for MariaDB availability."""
    available = _check_mariadb()
    if not available:
        pytest.skip("MariaDB is not available -- skipping parity tests")
    return True


@pytest.fixture()
def app(mariadb_available):
    """Create the Flask application with MariaDBTestingConfig.

    Each test gets a fresh app with clean tables.
    """
    app = create_app(MariaDBTestingConfig)

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db_session(app):
    """Provide a database session for the test.

    Yields db.session within the app context, and rolls back after the
    test for cleanup.
    """
    with app.app_context():
        yield _db.session
        _db.session.rollback()


@pytest.fixture()
def client(app):
    """Provide a Flask test client."""
    return app.test_client()


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
