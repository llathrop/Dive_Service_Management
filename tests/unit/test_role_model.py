"""Unit tests for the Role model."""

import pytest

from app.models.user import Role
from app.extensions import db as _db


pytestmark = pytest.mark.unit


def test_role_creation(app, db_session):
    """A role can be created with a name and description."""
    with app.app_context():
        role = Role(name="testrole", description="A test role")
        db_session.add(role)
        db_session.commit()

        assert role.id is not None
        assert role.name == "testrole"
        assert role.description == "A test role"


def test_role_repr(app, db_session):
    """The __repr__ returns '<Role 'name'>'."""
    with app.app_context():
        role = Role(name="reprrole", description="Repr test")
        db_session.add(role)
        db_session.commit()

        assert repr(role) == "<Role 'reprrole'>"
