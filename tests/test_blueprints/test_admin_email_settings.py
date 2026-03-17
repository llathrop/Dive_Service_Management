"""Tests for the Email settings tab in admin settings."""

import pytest

from app.extensions import db
from app.models.system_config import SystemConfig


def _seed_email_config(app):
    """Seed the email config keys for testing."""
    with app.app_context():
        entries = [
            ("email.enabled", "false", "boolean", "email"),
            ("email.smtp_server", "", "string", "email"),
            ("email.smtp_port", "587", "integer", "email"),
            ("email.smtp_use_tls", "true", "boolean", "email"),
            ("email.smtp_username", "", "string", "email"),
            ("email.smtp_password", "", "string", "email"),
            ("email.from_address", "", "string", "email"),
            ("email.from_name", "", "string", "email"),
        ]
        for key, value, config_type, category in entries:
            if not SystemConfig.query.filter_by(config_key=key).first():
                db.session.add(SystemConfig(
                    config_key=key,
                    config_value=value,
                    config_type=config_type,
                    category=category,
                ))
        db.session.commit()


class TestEmailSettingsTab:
    """Tests for the email settings admin tab."""

    def test_email_tab_requires_admin(self, logged_in_client):
        """Non-admin users cannot access email settings."""
        resp = logged_in_client.get("/admin/settings?tab=email")
        # logged_in_client is a regular user — should be 403
        assert resp.status_code == 403

    def test_email_tab_renders_for_admin(self, admin_client, app):
        """Admin can see the email settings tab."""
        _seed_email_config(app)
        resp = admin_client.get("/admin/settings?tab=email")
        assert resp.status_code == 200
        assert b"Email" in resp.data
        assert b"SMTP Server" in resp.data
        assert b"From Address" in resp.data

    def test_email_tab_shows_password_field(self, admin_client, app):
        """Password field renders with placeholder, not current value."""
        _seed_email_config(app)
        resp = admin_client.get("/admin/settings?tab=email")
        assert resp.status_code == 200
        assert b"Leave blank to keep current" in resp.data

    def test_email_tab_save_settings(self, admin_client, app):
        """Admin can save email settings."""
        _seed_email_config(app)
        resp = admin_client.post(
            "/admin/settings?tab=email",
            data={
                "tab": "email",
                "email_enabled": "y",
                "smtp_server": "smtp.test.com",
                "smtp_port": "587",
                "smtp_use_tls": "y",
                "smtp_username": "testuser",
                "smtp_password": "testpass",
                "from_address": "test@example.com",
                "from_name": "Test Sender",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Settings updated" in resp.data

        # Verify values persisted
        with app.app_context():
            row = SystemConfig.query.filter_by(config_key="email.smtp_server").first()
            assert row.config_value == "smtp.test.com"
            row = SystemConfig.query.filter_by(config_key="email.smtp_password").first()
            assert row.config_value == "testpass"

    def test_email_password_blank_keeps_current(self, admin_client, app):
        """Submitting with blank password preserves existing value."""
        _seed_email_config(app)

        # First set a password
        with app.app_context():
            row = SystemConfig.query.filter_by(config_key="email.smtp_password").first()
            row.config_value = "original_secret"
            db.session.commit()

        # Submit form with blank password
        resp = admin_client.post(
            "/admin/settings?tab=email",
            data={
                "tab": "email",
                "smtp_server": "smtp.test.com",
                "smtp_port": "587",
                "smtp_password": "",
                "from_address": "test@example.com",
                "from_name": "Test",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        # Password should be unchanged
        with app.app_context():
            row = SystemConfig.query.filter_by(config_key="email.smtp_password").first()
            assert row.config_value == "original_secret"

    def test_invalid_tab_falls_back_to_company(self, admin_client, app):
        """Invalid tab name falls back to company tab."""
        _seed_email_config(app)
        resp = admin_client.get("/admin/settings?tab=nonexistent")
        assert resp.status_code == 200
        assert b"Company" in resp.data


class TestEmailForm:
    """Tests for EmailSettingsForm field-level validation."""

    def test_form_validates_port_range(self, app):
        """Port must be between 1 and 65535."""
        from werkzeug.datastructures import MultiDict
        from app.forms.settings import EmailSettingsForm

        with app.test_request_context():
            form = EmailSettingsForm(
                formdata=MultiDict({"smtp_port": "99999"}),
                meta={"csrf": False},
            )
            form.validate()
            assert "smtp_port" in form.errors

    def test_form_validates_email_format(self, app):
        """from_address must be a valid email when provided."""
        from werkzeug.datastructures import MultiDict
        from app.forms.settings import EmailSettingsForm

        with app.test_request_context():
            form = EmailSettingsForm(
                formdata=MultiDict({"from_address": "not-an-email"}),
                meta={"csrf": False},
            )
            form.validate()
            assert "from_address" in form.errors

    def test_form_accepts_valid_data(self, app):
        """Valid form data passes validation."""
        from werkzeug.datastructures import MultiDict
        from app.forms.settings import EmailSettingsForm

        with app.test_request_context():
            form = EmailSettingsForm(
                formdata=MultiDict({
                    "smtp_server": "smtp.example.com",
                    "smtp_port": "587",
                    "from_address": "test@example.com",
                    "from_name": "Test",
                }),
                meta={"csrf": False},
            )
            valid = form.validate()
            assert "smtp_port" not in form.errors
            assert "from_address" not in form.errors
            assert valid
