"""Blueprint tests for saved search CRUD routes."""

import json

import pytest

from app.extensions import db
from app.models.saved_search import SavedSearch


class TestListSaved:
    """Tests for GET /search/saved."""

    def test_requires_auth(self, client):
        resp = client.get("/search/saved")
        assert resp.status_code == 302

    def test_returns_empty_list(self, logged_in_client):
        resp = logged_in_client.get("/search/saved")
        assert resp.status_code == 200
        assert resp.json == []

    def test_returns_user_searches(self, logged_in_client, app, db_session):
        # Create a search directly in DB for the logged-in user
        from app.models.user import User
        user = User.query.first()
        s = SavedSearch(
            user_id=user.id, name="Test", search_type="customer",
            filters_json='{"q": "test"}', is_default=False,
        )
        db.session.add(s)
        db.session.commit()

        resp = logged_in_client.get("/search/saved?type=customer")
        assert resp.status_code == 200
        data = resp.json
        assert len(data) == 1
        assert data[0]["name"] == "Test"
        assert data[0]["filters"] == {"q": "test"}

    def test_filters_by_type(self, logged_in_client, app, db_session):
        from app.models.user import User
        user = User.query.first()
        db.session.add(SavedSearch(
            user_id=user.id, name="Cust", search_type="customer",
            filters_json='{}', is_default=False,
        ))
        db.session.add(SavedSearch(
            user_id=user.id, name="Order", search_type="order",
            filters_json='{}', is_default=False,
        ))
        db.session.commit()

        resp = logged_in_client.get("/search/saved?type=order")
        assert len(resp.json) == 1
        assert resp.json[0]["name"] == "Order"


class TestCreateSaved:
    """Tests for POST /search/saved."""

    def test_requires_auth(self, client):
        resp = client.post("/search/saved", json={"name": "x", "search_type": "customer", "filters": {}})
        assert resp.status_code in (302, 401)

    def test_creates_search(self, logged_in_client):
        resp = logged_in_client.post(
            "/search/saved",
            json={"name": "My Search", "search_type": "customer", "filters": {"q": "active"}},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.json
        assert data["name"] == "My Search"
        assert data["filters"] == {"q": "active"}
        assert data["id"] is not None

    def test_rejects_empty_name(self, logged_in_client):
        resp = logged_in_client.post(
            "/search/saved",
            json={"name": "", "search_type": "customer", "filters": {}},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "Name is required" in resp.json["error"]

    def test_rejects_invalid_type(self, logged_in_client):
        resp = logged_in_client.post(
            "/search/saved",
            json={"name": "Bad", "search_type": "invalid", "filters": {}},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_rejects_duplicate_name(self, logged_in_client):
        logged_in_client.post(
            "/search/saved",
            json={"name": "Dup", "search_type": "customer", "filters": {}},
            content_type="application/json",
        )
        resp = logged_in_client.post(
            "/search/saved",
            json={"name": "Dup", "search_type": "customer", "filters": {}},
            content_type="application/json",
        )
        assert resp.status_code == 409

    def test_rejects_long_name(self, logged_in_client):
        resp = logged_in_client.post(
            "/search/saved",
            json={"name": "x" * 101, "search_type": "customer", "filters": {}},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "100 characters" in resp.json["error"]

    def test_rejects_non_dict_filters(self, logged_in_client):
        resp = logged_in_client.post(
            "/search/saved",
            json={"name": "Bad", "search_type": "customer", "filters": "not a dict"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_rejects_no_json_body(self, logged_in_client):
        resp = logged_in_client.post("/search/saved", data="not json")
        assert resp.status_code == 400


class TestUpdateSaved:
    """Tests for PUT /search/saved/<id>."""

    def test_updates_name(self, logged_in_client, db_session):
        # Create first
        resp = logged_in_client.post(
            "/search/saved",
            json={"name": "Old", "search_type": "customer", "filters": {}},
            content_type="application/json",
        )
        sid = resp.json["id"]

        resp = logged_in_client.put(
            f"/search/saved/{sid}",
            json={"name": "New"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json["name"] == "New"

    def test_returns_404_for_nonexistent(self, logged_in_client):
        resp = logged_in_client.put(
            "/search/saved/99999",
            json={"name": "x"},
            content_type="application/json",
        )
        assert resp.status_code == 404


class TestDeleteSaved:
    """Tests for DELETE /search/saved/<id>."""

    def test_deletes_search(self, logged_in_client, db_session):
        resp = logged_in_client.post(
            "/search/saved",
            json={"name": "ToDelete", "search_type": "customer", "filters": {}},
            content_type="application/json",
        )
        sid = resp.json["id"]

        resp = logged_in_client.delete(f"/search/saved/{sid}")
        assert resp.status_code == 200
        assert resp.json["ok"] is True

    def test_returns_404_for_nonexistent(self, logged_in_client):
        resp = logged_in_client.delete("/search/saved/99999")
        assert resp.status_code == 404


class TestSetDefault:
    """Tests for POST /search/saved/<id>/default."""

    def test_sets_default(self, logged_in_client, db_session):
        resp = logged_in_client.post(
            "/search/saved",
            json={"name": "DefaultMe", "search_type": "order", "filters": {}},
            content_type="application/json",
        )
        sid = resp.json["id"]

        resp = logged_in_client.post(f"/search/saved/{sid}/default")
        assert resp.status_code == 200
        assert resp.json["is_default"] is True

    def test_returns_404_for_nonexistent(self, logged_in_client):
        resp = logged_in_client.post("/search/saved/99999/default")
        assert resp.status_code == 404
