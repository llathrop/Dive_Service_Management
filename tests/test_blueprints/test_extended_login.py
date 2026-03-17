"""Tests for ExtendedLoginForm registration and remember-me functionality."""

import pytest
from flask_security import hash_password


@pytest.fixture()
def _user(app, db_session):
    """Create a test user for login tests."""
    with app.app_context():
        user_datastore = app.extensions["security"].datastore
        role = user_datastore.find_or_create_role(
            name="technician", description="Technician"
        )
        user = user_datastore.create_user(
            username="logintest",
            email="logintest@example.com",
            password=hash_password("password"),
            first_name="Login",
            last_name="Test",
        )
        user_datastore.add_role_to_user(user, role)
        db_session.commit()
        return user


class TestExtendedLoginForm:
    """Tests for the ExtendedLoginForm class."""

    def test_form_has_remember_field(self):
        """ExtendedLoginForm inherits the remember field from LoginForm."""
        from app.forms.auth import ExtendedLoginForm

        assert hasattr(ExtendedLoginForm, "remember")

    def test_form_is_registered_with_security(self, app):
        """ExtendedLoginForm is used as the login form by Flask-Security."""
        from app.forms.auth import ExtendedLoginForm

        login_form_class = app.extensions["security"].forms["login_form"].cls
        assert login_form_class is ExtendedLoginForm


class TestLoginPageRememberMe:
    """Tests for remember-me checkbox rendering on login page."""

    def test_login_page_renders_remember_checkbox(self, client):
        """Login page contains a remember-me checkbox."""
        response = client.get("/login")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Remember" in html
        assert "remember" in html

    @pytest.mark.usefixtures("_user")
    def test_login_with_remember_true(self, client):
        """Login succeeds when remember=True is submitted."""
        response = client.post(
            "/login",
            data={
                "email": "logintest@example.com",
                "password": "password",
                "remember": "y",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.location

    @pytest.mark.usefixtures("_user")
    def test_login_with_remember_false(self, client):
        """Login succeeds when remember field is omitted (False)."""
        response = client.post(
            "/login",
            data={
                "email": "logintest@example.com",
                "password": "password",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.location
