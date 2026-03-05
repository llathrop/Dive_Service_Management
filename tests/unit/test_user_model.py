"""Unit tests for the User model."""

import pytest
from flask_security import hash_password

from app.models.user import User


pytestmark = pytest.mark.unit


def test_user_creation(app, db_session):
    """A user can be created with all required fields."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        user = user_datastore.create_user(
            username="newuser",
            email="new@example.com",
            password=hash_password("password"),
            first_name="New",
            last_name="User",
        )
        db_session.commit()

        assert user.id is not None
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.first_name == "New"
        assert user.last_name == "User"
        assert user.active is True


def test_user_display_name(app, db_session):
    """The display_name property returns 'First Last'."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        user = user_datastore.create_user(
            username="displayuser",
            email="display@example.com",
            password=hash_password("password"),
            first_name="Jane",
            last_name="Doe",
        )
        db_session.commit()

        assert user.display_name == "Jane Doe"


def test_user_repr(app, db_session):
    """The __repr__ returns '<User 'username'>'."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        user = user_datastore.create_user(
            username="repruser",
            email="repr@example.com",
            password=hash_password("password"),
            first_name="Repr",
            last_name="Test",
        )
        db_session.commit()

        assert repr(user) == "<User 'repruser'>"


def test_user_roles_relationship(app, db_session):
    """A user can be assigned a role via the datastore."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        role = user_datastore.find_or_create_role(
            name="viewer", description="Read-only access"
        )
        user = user_datastore.create_user(
            username="roleuser",
            email="role@example.com",
            password=hash_password("password"),
            first_name="Role",
            last_name="Test",
        )
        user_datastore.add_role_to_user(user, role)
        db_session.commit()

        assert len(user.roles) == 1
        assert user.roles[0].name == "viewer"


def test_user_is_active_property(app, db_session):
    """The is_active property proxies the active column and supports setting."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        user = user_datastore.create_user(
            username="activeuser",
            email="active@example.com",
            password=hash_password("password"),
            first_name="Active",
            last_name="Test",
        )
        db_session.commit()

        # Default is active
        assert user.is_active is True

        # Deactivate via property
        user.is_active = False
        db_session.commit()
        assert user.active is False
        assert user.is_active is False


def test_user_fs_uniquifier_auto_generated(app, db_session):
    """The fs_uniquifier field is automatically set when creating a user."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        user = user_datastore.create_user(
            username="uniquser",
            email="uniq@example.com",
            password=hash_password("password"),
            first_name="Uniq",
            last_name="Test",
        )
        db_session.commit()

        assert user.fs_uniquifier is not None
        assert len(user.fs_uniquifier) > 0


def test_user_timestamps(app, db_session):
    """TimestampMixin provides a created_at timestamp that is set on creation."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        user = user_datastore.create_user(
            username="tsuser",
            email="ts@example.com",
            password=hash_password("password"),
            first_name="Timestamp",
            last_name="Test",
        )
        db_session.commit()

        assert user.created_at is not None
