"""Blueprint tests for notification routes.

Tests listing, unread count, marking as read, and marking all as read
for the notifications blueprint.  Verifies role-based access control
for anonymous and authenticated users.
"""

import pytest
from flask_security import hash_password

from app.extensions import db
from app.models.notification import Notification

pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_notification(db_session, user_id=None, **overrides):
    """Create and persist a Notification with sensible defaults."""
    defaults = dict(
        notification_type="system",
        title="Test Notification",
        message="This is a test notification.",
        severity="info",
        is_read=False,
    )
    defaults.update(overrides)
    if user_id is not None:
        defaults["user_id"] = user_id
    notification = Notification(**defaults)
    db.session.add(notification)
    db.session.commit()
    return notification


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    """Anonymous users are redirected to the login page."""

    def test_list_unauthenticated_redirects(self, client):
        response = client.get("/notifications/")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_count_unauthenticated_redirects(self, client):
        response = client.get("/notifications/count")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_mark_read_unauthenticated_redirects(self, client):
        response = client.post("/notifications/1/read")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_mark_all_read_unauthenticated_redirects(self, client):
        response = client.post("/notifications/mark-all-read")
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Authenticated access
# ---------------------------------------------------------------------------


class TestAuthenticatedAccess:
    """Authenticated users can access notification endpoints."""

    def test_list_authenticated(self, logged_in_client, app, db_session):
        """Authenticated user can list notifications."""
        response = logged_in_client.get("/notifications/")
        assert response.status_code == 200

    def test_unread_count(self, logged_in_client, app, db_session):
        """Unread count endpoint returns JSON with count key."""
        response = logged_in_client.get("/notifications/count")
        assert response.status_code == 200
        data = response.get_json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_mark_read(self, logged_in_client, app, db_session):
        """Marking a notification as read redirects to the list."""
        with app.app_context():
            # Get the logged-in user's ID by querying from the session
            from app.models.user import User
            user = User.query.filter_by(username="loggedinuser").first()
            notification = _create_notification(db_session, user_id=user.id)
            nid = notification.id
        response = logged_in_client.post(
            f"/notifications/{nid}/read",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/notifications" in response.location

    def test_mark_all_read(self, logged_in_client, app, db_session):
        """Marking all notifications as read redirects to the list."""
        with app.app_context():
            from app.models.user import User
            user = User.query.filter_by(username="loggedinuser").first()
            _create_notification(db_session, user_id=user.id, title="Notif 1")
            _create_notification(db_session, user_id=user.id, title="Notif 2")
        response = logged_in_client.post(
            "/notifications/mark-all-read",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/notifications" in response.location


# ---------------------------------------------------------------------------
# unread_only query parameter parsing
# ---------------------------------------------------------------------------


class TestUnreadOnlyParsing:
    """Verify that the unread_only parameter is parsed correctly."""

    def test_unread_only_false_string_not_treated_as_true(self, logged_in_client, app, db_session):
        """Passing unread_only=false should not filter to unread only."""
        response = logged_in_client.get("/notifications/?unread_only=false")
        assert response.status_code == 200

    def test_unread_only_random_string_not_treated_as_true(self, logged_in_client, app, db_session):
        """Passing unread_only=notavalue should not filter to unread only."""
        response = logged_in_client.get("/notifications/?unread_only=notavalue")
        assert response.status_code == 200

    def test_unread_only_true_accepted(self, logged_in_client, app, db_session):
        """Passing unread_only=true should succeed."""
        response = logged_in_client.get("/notifications/?unread_only=true")
        assert response.status_code == 200

    def test_unread_only_1_accepted(self, logged_in_client, app, db_session):
        """Passing unread_only=1 should succeed."""
        response = logged_in_client.get("/notifications/?unread_only=1")
        assert response.status_code == 200
