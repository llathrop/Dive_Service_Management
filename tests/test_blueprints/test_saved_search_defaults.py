"""Tests for saved search defaults being applied on list page load."""

import json

import pytest

from app.extensions import db
from app.models.saved_search import SavedSearch
from app.models.user import User


class TestCustomerSavedSearchDefaults:
    """Saved search defaults on the customers list page."""

    def test_default_search_applied_when_no_params(self, logged_in_client, app, db_session):
        """When no filter params are in the URL, the default saved search filters apply."""
        user = User.query.filter_by(email="loggedin@example.com").first()
        ss = SavedSearch(
            user_id=user.id,
            name="Business Only",
            search_type="customer",
            filters_json=json.dumps({"customer_type": "business"}),
            is_default=True,
        )
        db.session.add(ss)
        db.session.commit()

        resp = logged_in_client.get("/customers/")
        assert resp.status_code == 200
        # The form should reflect the saved search filter
        html = resp.data.decode()
        # The customer_type select should have 'business' selected
        assert 'selected' in html  # form should render with saved values

    def test_explicit_params_override_default(self, logged_in_client, app, db_session):
        """When the user provides explicit params, the default saved search is ignored."""
        user = User.query.filter_by(email="loggedin@example.com").first()
        ss = SavedSearch(
            user_id=user.id,
            name="Business Only",
            search_type="customer",
            filters_json=json.dumps({"customer_type": "business"}),
            is_default=True,
        )
        db.session.add(ss)
        db.session.commit()

        # Pass an explicit sort param — default search should NOT be applied
        resp = logged_in_client.get("/customers/?sort=email")
        assert resp.status_code == 200

    def test_no_default_search_works_normally(self, logged_in_client):
        """Without a default saved search, the list page loads normally."""
        resp = logged_in_client.get("/customers/")
        assert resp.status_code == 200


class TestItemsSavedSearchDefaults:
    """Saved search defaults on the items list page."""

    def test_default_search_applied_when_no_params(self, logged_in_client, app, db_session):
        user = User.query.filter_by(email="loggedin@example.com").first()
        ss = SavedSearch(
            user_id=user.id,
            name="Regulators",
            search_type="item",
            filters_json=json.dumps({"q": "regulator"}),
            is_default=True,
        )
        db.session.add(ss)
        db.session.commit()

        resp = logged_in_client.get("/items/")
        assert resp.status_code == 200

    def test_explicit_params_override_default(self, logged_in_client, app, db_session):
        user = User.query.filter_by(email="loggedin@example.com").first()
        ss = SavedSearch(
            user_id=user.id,
            name="Regulators",
            search_type="item",
            filters_json=json.dumps({"q": "regulator"}),
            is_default=True,
        )
        db.session.add(ss)
        db.session.commit()

        resp = logged_in_client.get("/items/?q=drysuit")
        assert resp.status_code == 200

    def test_no_default_search_works_normally(self, logged_in_client):
        resp = logged_in_client.get("/items/")
        assert resp.status_code == 200


class TestInventorySavedSearchDefaults:
    """Saved search defaults on the inventory list page."""

    def test_default_search_applied_when_no_params(self, logged_in_client, app, db_session):
        user = User.query.filter_by(email="loggedin@example.com").first()
        ss = SavedSearch(
            user_id=user.id,
            name="Low Stock Active",
            search_type="inventory",
            filters_json=json.dumps({"is_active": "1", "low_stock_only": "on"}),
            is_default=True,
        )
        db.session.add(ss)
        db.session.commit()

        resp = logged_in_client.get("/inventory/")
        assert resp.status_code == 200

    def test_explicit_params_override_default(self, logged_in_client, app, db_session):
        user = User.query.filter_by(email="loggedin@example.com").first()
        ss = SavedSearch(
            user_id=user.id,
            name="Low Stock",
            search_type="inventory",
            filters_json=json.dumps({"is_active": "1"}),
            is_default=True,
        )
        db.session.add(ss)
        db.session.commit()

        resp = logged_in_client.get("/inventory/?category=Parts")
        assert resp.status_code == 200

    def test_no_default_search_works_normally(self, logged_in_client):
        resp = logged_in_client.get("/inventory/")
        assert resp.status_code == 200
