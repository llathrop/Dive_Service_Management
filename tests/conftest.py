"""Shared pytest fixtures for the Dive Service Management test suite.

Provides app, client, db_session, runner, auth_user, admin_user,
and logged_in_client fixtures used across all test modules.
"""

import pytest
from flask_security import hash_password

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from tests._fixtures import (
    _login_client,
    make_auth_user_fixture,
    make_client_fixture,
    make_db_session_fixture,
)


@pytest.fixture()
def app():
    """Create the Flask application with TestingConfig.

    Each test gets a fresh app with clean tables.
    """
    app = create_app(TestingConfig)

    with app.app_context():
        _db.create_all()
        
        # Seed lookup values for drysuit forms and choices
        from app.models.lookup import LookupValue
        from app.cli.seed_lookups import DRYSUIT_LOOKUPS
        
        # Build a safe deep copy of lookups to avoid modifying shared module references
        test_lookups = {}
        for cat, pairs in DRYSUIT_LOOKUPS.items():
            test_lookups[cat] = list(pairs)
            
        # Append test-specific values safely
        if ("Back-entry", "Back-entry") not in test_lookups.setdefault("suit_entry_type", []):
            test_lookups["suit_entry_type"].append(("Back-entry", "Back-entry"))
        if ("Integrated Rock Boot", "Integrated Rock Boot") not in test_lookups.setdefault("boot_type", []):
            test_lookups["boot_type"].append(("Integrated Rock Boot", "Integrated Rock Boot"))
            
        test_lookups["zipper_orientation"] = [
            ("Front", "Front"),
            ("Rear", "Rear"),
            ("Shoulder", "Shoulder"),
            ("Diagonal", "Diagonal"),
            ("Back", "Back")
        ]
        test_lookups["dump_valve_type"] = [
            ("Shoulder", "Shoulder"),
            ("Wrist", "Wrist"),
            ("Ankle", "Ankle")
        ]
        
        # Deduplicate and add to session
        for category, pairs in test_lookups.items():
            seen = set()
            for value, display_name in pairs:
                if value in seen:
                    continue
                seen.add(value)
                lv = LookupValue(
                    category=category,
                    value=value,
                    display_name=display_name,
                    is_active=True
                )
                _db.session.add(lv)
        _db.session.commit()
        
        yield app
        _db.session.remove()
        _db.drop_all()


db_session = make_db_session_fixture()
client = make_client_fixture()
auth_user = make_auth_user_fixture()


@pytest.fixture()
def runner(app):
    """Provide a Flask CLI test runner."""
    return app.test_cli_runner()


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
