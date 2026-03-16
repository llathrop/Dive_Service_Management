"""Tests for the dashboard activity feed feature."""

import pytest

from tests.factories import AuditLogFactory, UserFactory


class TestDashboardActivityFeed:
    """Tests for the activity feed on GET /dashboard/."""

    def test_dashboard_includes_activity_feed_section(self, logged_in_client):
        """Dashboard page contains the activity feed container."""
        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"Recent Activity" in resp.data
        assert b'id="activity-feed"' in resp.data

    def test_dashboard_shows_audit_entries(self, logged_in_client, db_session):
        """Activity feed displays recent audit log entries."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(
            action="create",
            entity_type="customer",
            entity_id=42,
        )
        db_session.flush()

        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"Customer #42" in resp.data
        assert b"Create" in resp.data

    def test_dashboard_empty_state(self, logged_in_client):
        """When no audit entries exist, show empty state message."""
        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"No activity yet" in resp.data

    def test_htmx_polling_attributes(self, logged_in_client):
        """Activity feed div has HTMX polling attributes."""
        resp = logged_in_client.get("/dashboard/")
        html = resp.data.decode()
        assert 'hx-get="/dashboard/activity-feed"' in html
        assert 'hx-trigger="every 60s"' in html

    def test_admin_sees_view_all_link(self, admin_client):
        """Admin users see the View All link to the audit log."""
        resp = admin_client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"/admin/audit-log" in resp.data
        assert b"View All" in resp.data

    def test_non_admin_no_view_all_link(self, logged_in_client):
        """Non-admin users do not see the View All link."""
        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"/admin/audit-log" not in resp.data

    def test_activity_shows_user_name(self, app, logged_in_client, db_session):
        """Activity feed displays the user who performed the action."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        user = db_session.execute(
            __import__("sqlalchemy").text(
                "SELECT id, first_name FROM users WHERE first_name = 'Logged'"
            )
        ).first()
        AuditLogFactory(
            action="update",
            entity_type="customer",
            entity_id=1,
            user_id=user.id,
            field_name="name",
            old_value="Old Name",
            new_value="New Name",
        )
        db_session.flush()

        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"Logged" in resp.data

    def test_activity_shows_system_for_null_user(self, logged_in_client, db_session):
        """Entries without a user_id display 'System'."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(
            action="create",
            entity_type="customer",
            entity_id=1,
            user_id=None,
        )
        db_session.flush()

        resp = logged_in_client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"System" in resp.data

    def test_activity_action_badges(self, logged_in_client, db_session):
        """Different actions get different colored badges."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=1)
        AuditLogFactory(action="update", entity_type="customer", entity_id=2)
        AuditLogFactory(action="delete", entity_type="customer", entity_id=3)
        AuditLogFactory(
            action="status_change",
            entity_type="service_order",
            entity_id=4,
            old_value="intake",
            new_value="assessment",
        )
        db_session.flush()

        resp = logged_in_client.get("/dashboard/")
        html = resp.data.decode()
        assert "bg-success" in html  # create
        assert "bg-primary" in html  # update
        assert "bg-danger" in html  # delete
        assert "bg-warning" in html  # status_change

    def test_status_change_description(self, logged_in_client, db_session):
        """Status change entries show old -> new status."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(
            action="status_change",
            entity_type="service_order",
            entity_id=10,
            old_value="intake",
            new_value="assessment",
        )
        db_session.flush()

        resp = logged_in_client.get("/dashboard/")
        html = resp.data.decode()
        assert "intake" in html
        assert "assessment" in html


class TestActivityFeedPartial:
    """Tests for the HTMX partial endpoint GET /dashboard/activity-feed."""

    def test_partial_returns_html_fragment(self, logged_in_client):
        """The partial endpoint returns HTML without full page layout."""
        resp = logged_in_client.get("/dashboard/activity-feed")
        assert resp.status_code == 200
        # Should NOT contain full page elements
        assert b"<!DOCTYPE" not in resp.data
        assert b"<html" not in resp.data

    def test_partial_shows_entries(self, logged_in_client, db_session):
        """The partial endpoint includes audit entries."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=99)
        db_session.flush()

        resp = logged_in_client.get("/dashboard/activity-feed")
        assert resp.status_code == 200
        assert b"Customer #99" in resp.data

    def test_partial_empty_state(self, logged_in_client):
        """The partial endpoint shows empty state when no entries exist."""
        resp = logged_in_client.get("/dashboard/activity-feed")
        assert resp.status_code == 200
        assert b"No activity yet" in resp.data

    def test_partial_requires_login(self, client):
        """The partial endpoint requires authentication."""
        resp = client.get("/dashboard/activity-feed")
        # Should redirect to login
        assert resp.status_code == 302
        assert "/login" in resp.location
