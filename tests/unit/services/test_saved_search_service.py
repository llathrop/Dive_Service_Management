"""Unit tests for the saved search service layer."""

import pytest
from flask_security import hash_password

from app.extensions import db
from app.models.saved_search import SavedSearch
from app.services import saved_search_service

pytestmark = pytest.mark.unit


def _make_user(app, db_session, username="ss_user", email="ss@example.com"):
    """Create a test user via user_datastore."""
    user_datastore = app.extensions["security"].datastore
    user_datastore.find_or_create_role(name="admin", description="Admin")
    user = user_datastore.create_user(
        username=username,
        email=email,
        password=hash_password("password"),
        first_name="Search",
        last_name="Tester",
    )
    db_session.commit()
    return user


class TestCreateSearch:
    """Tests for create_search()."""

    def test_creates_saved_search(self, app, db_session):
        user = _make_user(app, db_session)
        result = saved_search_service.create_search(
            user_id=user.id,
            name="Active Customers",
            search_type="customer",
            filters={"q": "active"},
        )
        assert result is not None
        assert result.name == "Active Customers"
        assert result.search_type == "customer"
        assert result.filters == {"q": "active"}
        assert result.is_default is False

    def test_creates_with_default(self, app, db_session):
        user = _make_user(app, db_session)
        result = saved_search_service.create_search(
            user_id=user.id,
            name="Default",
            search_type="customer",
            filters={},
            is_default=True,
        )
        assert result.is_default is True

    def test_rejects_invalid_search_type(self, app, db_session):
        user = _make_user(app, db_session)
        with pytest.raises(ValueError, match="Invalid search type"):
            saved_search_service.create_search(
                user_id=user.id, name="Bad", search_type="invalid", filters={}
            )

    def test_duplicate_name_returns_none(self, app, db_session):
        user = _make_user(app, db_session)
        saved_search_service.create_search(
            user_id=user.id, name="Dup", search_type="customer", filters={}
        )
        result = saved_search_service.create_search(
            user_id=user.id, name="Dup", search_type="customer", filters={}
        )
        assert result is None

    def test_same_name_different_type_allowed(self, app, db_session):
        user = _make_user(app, db_session)
        saved_search_service.create_search(
            user_id=user.id, name="Recent", search_type="customer", filters={}
        )
        result = saved_search_service.create_search(
            user_id=user.id, name="Recent", search_type="order", filters={}
        )
        assert result is not None

    def test_set_default_clears_previous(self, app, db_session):
        user = _make_user(app, db_session)
        s1 = saved_search_service.create_search(
            user_id=user.id, name="First", search_type="customer",
            filters={}, is_default=True,
        )
        s2 = saved_search_service.create_search(
            user_id=user.id, name="Second", search_type="customer",
            filters={}, is_default=True,
        )
        db_session.refresh(s1)
        assert s1.is_default is False
        assert s2.is_default is True


class TestGetUserSearches:
    """Tests for get_user_searches()."""

    def test_returns_all_for_user(self, app, db_session):
        user = _make_user(app, db_session)
        saved_search_service.create_search(user.id, "A", "customer", {})
        saved_search_service.create_search(user.id, "B", "order", {})

        results = saved_search_service.get_user_searches(user.id)
        assert len(results) == 2

    def test_filters_by_type(self, app, db_session):
        user = _make_user(app, db_session)
        saved_search_service.create_search(user.id, "A", "customer", {})
        saved_search_service.create_search(user.id, "B", "order", {})

        results = saved_search_service.get_user_searches(user.id, search_type="customer")
        assert len(results) == 1
        assert results[0].search_type == "customer"

    def test_does_not_return_other_users(self, app, db_session):
        user1 = _make_user(app, db_session, "u1", "u1@example.com")
        user2 = _make_user(app, db_session, "u2", "u2@example.com")
        saved_search_service.create_search(user1.id, "Mine", "customer", {})

        results = saved_search_service.get_user_searches(user2.id)
        assert len(results) == 0


class TestUpdateSearch:
    """Tests for update_search()."""

    def test_updates_name(self, app, db_session):
        user = _make_user(app, db_session)
        s = saved_search_service.create_search(user.id, "Old", "customer", {})
        result = saved_search_service.update_search(s.id, user.id, name="New")
        assert result.name == "New"

    def test_updates_filters(self, app, db_session):
        user = _make_user(app, db_session)
        s = saved_search_service.create_search(user.id, "Test", "customer", {"q": "old"})
        result = saved_search_service.update_search(s.id, user.id, filters={"q": "new"})
        assert result.filters == {"q": "new"}

    def test_returns_none_for_wrong_user(self, app, db_session):
        user1 = _make_user(app, db_session, "uu1", "uu1@example.com")
        user2 = _make_user(app, db_session, "uu2", "uu2@example.com")
        s = saved_search_service.create_search(user1.id, "Test", "customer", {})
        result = saved_search_service.update_search(s.id, user2.id, name="Stolen")
        assert result is None


class TestDeleteSearch:
    """Tests for delete_search()."""

    def test_deletes_own_search(self, app, db_session):
        user = _make_user(app, db_session)
        s = saved_search_service.create_search(user.id, "ToDelete", "customer", {})
        assert saved_search_service.delete_search(s.id, user.id) is True
        assert SavedSearch.query.get(s.id) is None

    def test_cannot_delete_other_users_search(self, app, db_session):
        user1 = _make_user(app, db_session, "d1", "d1@example.com")
        user2 = _make_user(app, db_session, "d2", "d2@example.com")
        s = saved_search_service.create_search(user1.id, "Mine", "customer", {})
        assert saved_search_service.delete_search(s.id, user2.id) is False


class TestSetDefault:
    """Tests for set_default()."""

    def test_sets_default_and_clears_previous(self, app, db_session):
        user = _make_user(app, db_session)
        s1 = saved_search_service.create_search(user.id, "S1", "order", {}, is_default=True)
        s2 = saved_search_service.create_search(user.id, "S2", "order", {})

        result = saved_search_service.set_default(s2.id, user.id)
        db_session.refresh(s1)
        assert result.is_default is True
        assert s1.is_default is False


class TestGetDefaultSearch:
    """Tests for get_default_search()."""

    def test_returns_default(self, app, db_session):
        user = _make_user(app, db_session)
        saved_search_service.create_search(user.id, "Default", "invoice", {}, is_default=True)
        saved_search_service.create_search(user.id, "Other", "invoice", {})

        result = saved_search_service.get_default_search(user.id, "invoice")
        assert result is not None
        assert result.name == "Default"

    def test_returns_none_when_no_default(self, app, db_session):
        user = _make_user(app, db_session)
        saved_search_service.create_search(user.id, "NoDefault", "invoice", {})

        result = saved_search_service.get_default_search(user.id, "invoice")
        assert result is None
