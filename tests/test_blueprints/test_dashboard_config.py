"""Tests for dashboard customization (card visibility and ordering)."""

import json

import pytest

from app.extensions import db
from app.models.user import User


class TestDashboardConfigEndpoint:
    """Tests for POST /dashboard/config."""

    def test_save_config(self, logged_in_client, app, db_session):
        """Saving dashboard config persists to the user model."""
        config = {
            "visible_cards": ["open_orders", "low_stock"],
            "card_order": ["low_stock", "open_orders", "awaiting_pickup", "overdue_invoices", "recent_activity"],
        }
        resp = logged_in_client.post(
            "/dashboard/config",
            data=json.dumps(config),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json["status"] == "ok"

        # Verify it was persisted
        user = User.query.filter_by(email="loggedin@example.com").first()
        saved = json.loads(user.dashboard_config)
        assert saved["visible_cards"] == ["open_orders", "low_stock"]
        assert saved["card_order"][0] == "low_stock"

    def test_config_requires_login(self, client):
        """The config endpoint requires authentication."""
        resp = client.post(
            "/dashboard/config",
            data=json.dumps({"visible_cards": []}),
            content_type="application/json",
        )
        assert resp.status_code in (302, 401)

    def test_invalid_json_returns_error(self, logged_in_client):
        """Posting non-JSON content returns an error status."""
        resp = logged_in_client.post(
            "/dashboard/config",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_invalid_card_ids_filtered(self, logged_in_client, app, db_session):
        """Unknown card IDs are silently filtered out."""
        config = {
            "visible_cards": ["open_orders", "bogus_card"],
            "card_order": ["open_orders", "bogus_card"],
        }
        resp = logged_in_client.post(
            "/dashboard/config",
            data=json.dumps(config),
            content_type="application/json",
        )
        assert resp.status_code == 200

        user = User.query.filter_by(email="loggedin@example.com").first()
        saved = json.loads(user.dashboard_config)
        assert "bogus_card" not in saved["visible_cards"]
        assert "bogus_card" not in saved["card_order"]


class TestDashboardWithConfig:
    """Tests for GET /dashboard/ with and without saved config."""

    def test_dashboard_with_saved_config(self, logged_in_client, app, db_session):
        """Dashboard renders correctly when user has a saved config."""
        user = User.query.filter_by(email="loggedin@example.com").first()
        user.dashboard_config = json.dumps({
            "visible_cards": ["open_orders", "low_stock"],
            "card_order": ["low_stock", "open_orders", "awaiting_pickup", "overdue_invoices", "recent_activity"],
        })
        db.session.commit()

        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        html = resp.data.decode()
        # open_orders and low_stock should be visible
        assert "Open Orders" in html
        assert "Low Stock" in html

    def test_dashboard_without_config_shows_defaults(self, logged_in_client):
        """Dashboard shows all cards when no config is saved."""
        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Open Orders" in html
        assert "Awaiting Pickup" in html
        assert "Low Stock" in html
        assert "Overdue Invoices" in html
        assert "Recent Activity" in html

    def test_dashboard_with_empty_visible_hides_stat_cards(self, logged_in_client, app, db_session):
        """When no stat cards are visible, they should not render."""
        user = User.query.filter_by(email="loggedin@example.com").first()
        user.dashboard_config = json.dumps({
            "visible_cards": ["recent_activity"],
            "card_order": ["recent_activity"],
        })
        db.session.commit()

        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        html = resp.data.decode()
        # Stat cards should NOT appear
        assert "Active service orders" not in html
        # Recent activity should still be present
        assert "Recent Activity" in html

    def test_customize_button_present(self, logged_in_client):
        """The customize button should appear on the dashboard."""
        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"Customize" in resp.data
