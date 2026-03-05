"""Blueprint tests for admin routes."""

import pytest


pytestmark = pytest.mark.blueprint


# ── Access control ──────────────────────────────────────────────────

class TestAdminAccess:
    """Admin pages require admin role."""

    def test_admin_hub_requires_login(self, client):
        """GET /admin/ without login redirects or returns 403."""
        response = client.get("/admin/")
        # Flask-Security may return 302 (redirect to login) or 403
        assert response.status_code in (302, 403)

    def test_admin_hub_requires_admin_role(self, logged_in_client):
        """Technician cannot access admin hub (403)."""
        response = logged_in_client.get("/admin/")
        assert response.status_code == 403

    def test_admin_hub_accessible_by_admin(self, admin_client):
        """Admin user can access admin hub."""
        response = admin_client.get("/admin/")
        assert response.status_code == 200
        assert b"Administration" in response.data

    def test_viewer_cannot_access_admin(self, viewer_client):
        """Viewer cannot access admin hub (403)."""
        response = viewer_client.get("/admin/")
        assert response.status_code == 403


# ── Admin Hub ───────────────────────────────────────────────────────

class TestAdminHub:
    """Tests for the admin hub page."""

    def test_hub_shows_user_count(self, admin_client):
        """Admin hub shows user count."""
        response = admin_client.get("/admin/")
        assert b"User Management" in response.data

    def test_hub_has_links_to_subpages(self, admin_client):
        """Admin hub links to users, settings, data."""
        response = admin_client.get("/admin/")
        html = response.data.decode()
        assert "/admin/users" in html
        assert "/admin/settings" in html
        assert "/admin/data" in html


# ── User Management ────────────────────────────────────────────────

class TestUserList:
    """Tests for user list page."""

    def test_user_list_shows_users(self, admin_client):
        """User list page returns 200 and shows users."""
        response = admin_client.get("/admin/users")
        assert response.status_code == 200
        assert b"User Management" in response.data

    def test_user_list_forbidden_for_tech(self, logged_in_client):
        """Technician cannot access user list."""
        response = logged_in_client.get("/admin/users")
        assert response.status_code == 403


class TestCreateUser:
    """Tests for creating users."""

    def test_create_user_form_loads(self, admin_client):
        """GET /admin/users/new shows the user creation form."""
        response = admin_client.get("/admin/users/new")
        assert response.status_code == 200
        assert b"New User" in response.data

    def test_create_user_success(self, admin_client):
        """POST /admin/users/new with valid data creates user."""
        response = admin_client.post(
            "/admin/users/new",
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "first_name": "New",
                "last_name": "User",
                "password": "SecurePass123",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"created successfully" in response.data

    def test_create_user_missing_fields(self, admin_client):
        """POST with missing required fields shows errors."""
        response = admin_client.post(
            "/admin/users/new",
            data={
                "username": "",
                "email": "",
                "first_name": "",
                "last_name": "",
                "password": "",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"required" in response.data

    def test_create_user_short_password(self, admin_client):
        """POST with short password shows error."""
        response = admin_client.post(
            "/admin/users/new",
            data={
                "username": "shortpw",
                "email": "shortpw@example.com",
                "first_name": "Short",
                "last_name": "Password",
                "password": "abc",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"at least 8 characters" in response.data

    def test_create_user_duplicate_username(self, admin_client):
        """POST with existing username shows error."""
        # Create first user
        admin_client.post(
            "/admin/users/new",
            data={
                "username": "dupuser",
                "email": "dup1@example.com",
                "first_name": "Dup",
                "last_name": "User",
                "password": "SecurePass123",
            },
        )
        # Try duplicate username
        response = admin_client.post(
            "/admin/users/new",
            data={
                "username": "dupuser",
                "email": "dup2@example.com",
                "first_name": "Dup",
                "last_name": "Two",
                "password": "SecurePass123",
            },
            follow_redirects=True,
        )
        assert b"already exists" in response.data


class TestEditUser:
    """Tests for editing users."""

    def test_edit_user_form_loads(self, admin_client):
        """Create a user and load their edit form."""
        # Create a user
        admin_client.post(
            "/admin/users/new",
            data={
                "username": "editme",
                "email": "editme@example.com",
                "first_name": "Edit",
                "last_name": "Me",
                "password": "SecurePass123",
            },
        )
        # Find the user id by listing
        from app.models.user import User
        user = User.query.filter_by(username="editme").first()
        assert user is not None
        response = admin_client.get(f"/admin/users/{user.id}/edit")
        assert response.status_code == 200
        assert b"Edit User" in response.data

    def test_edit_nonexistent_user_redirects(self, admin_client):
        """Editing a nonexistent user redirects with error."""
        response = admin_client.get("/admin/users/99999/edit", follow_redirects=True)
        assert b"not found" in response.data


class TestToggleUserActive:
    """Tests for activating/deactivating users."""

    def test_toggle_deactivates_user(self, admin_client):
        """POST toggle-active deactivates an active user."""
        admin_client.post(
            "/admin/users/new",
            data={
                "username": "toggleme",
                "email": "toggleme@example.com",
                "first_name": "Toggle",
                "last_name": "Me",
                "password": "SecurePass123",
            },
        )
        from app.models.user import User
        user = User.query.filter_by(username="toggleme").first()
        response = admin_client.post(
            f"/admin/users/{user.id}/toggle-active",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"deactivated" in response.data


# ── Settings ────────────────────────────────────────────────────────

class TestSettings:
    """Tests for settings page."""

    def test_settings_page_loads(self, admin_client):
        """GET /admin/settings returns 200."""
        response = admin_client.get("/admin/settings")
        assert response.status_code == 200
        assert b"System Settings" in response.data

    def test_settings_forbidden_for_tech(self, logged_in_client):
        """Technician cannot access settings."""
        response = logged_in_client.get("/admin/settings")
        assert response.status_code == 403


# ── Data Management ─────────────────────────────────────────────────

class TestDataManagement:
    """Tests for data management page."""

    def test_data_page_loads(self, admin_client):
        """GET /admin/data returns 200 with statistics."""
        response = admin_client.get("/admin/data")
        assert response.status_code == 200
        assert b"Data Management" in response.data
        assert b"Backup" in response.data

    def test_data_forbidden_for_tech(self, logged_in_client):
        """Technician cannot access data management."""
        response = logged_in_client.get("/admin/data")
        assert response.status_code == 403
