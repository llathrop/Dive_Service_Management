"""Unit tests for the email service."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestGetSmtpConfig:
    """Tests for _get_smtp_config()."""

    def test_returns_none_when_disabled(self, app):
        """Returns None when email.enabled is False."""
        from app.services.email_service import _get_smtp_config

        with app.app_context():
            with patch("app.services.email_service.config_service") as mock_config:
                mock_config.get_config.return_value = False
                assert _get_smtp_config() is None

    def test_returns_none_when_no_server(self, app):
        """Returns None when email is enabled but no server configured."""
        from app.services.email_service import _get_smtp_config

        with app.app_context():
            with patch("app.services.email_service.config_service") as mock_config:
                def config_side_effect(key, default=None):
                    if key == "email.enabled":
                        return True
                    if key == "email.smtp_server":
                        return ""
                    return default
                mock_config.get_config.side_effect = config_side_effect
                assert _get_smtp_config() is None

    def test_returns_config_dict_when_valid(self, app):
        """Returns full config dict when properly configured."""
        from app.services.email_service import _get_smtp_config

        with app.app_context():
            with patch("app.services.email_service.config_service") as mock_config:
                config_values = {
                    "email.enabled": True,
                    "email.smtp_server": "smtp.example.com",
                    "email.smtp_port": 587,
                    "email.smtp_use_tls": True,
                    "email.smtp_username": "user@example.com",
                    "email.smtp_password": "secret",
                    "email.from_address": "noreply@example.com",
                    "email.from_name": "Test App",
                }
                mock_config.get_config.side_effect = lambda k, d=None: config_values.get(k, d)
                result = _get_smtp_config()
                assert result is not None
                assert result["server"] == "smtp.example.com"
                assert result["port"] == 587
                assert result["use_tls"] is True
                assert result["from_address"] == "noreply@example.com"


class TestSendEmail:
    """Tests for send_email()."""

    def test_returns_false_when_disabled(self, app):
        """Returns False when email is disabled."""
        from app.services.email_service import send_email

        with app.app_context():
            with patch("app.services.email_service._get_smtp_config", return_value=None):
                result = send_email("to@example.com", "Subject", "<p>Body</p>")
                assert result is False

    def test_returns_false_when_no_from_address(self, app):
        """Returns False when no from_address configured."""
        from app.services.email_service import send_email

        config = {
            "server": "smtp.example.com", "port": 587, "use_tls": True,
            "username": "", "password": "", "from_address": "", "from_name": "",
        }
        with app.app_context():
            with patch("app.services.email_service._get_smtp_config", return_value=config):
                result = send_email("to@example.com", "Subject", "<p>Body</p>")
                assert result is False

    @patch("app.services.email_service.smtplib.SMTP")
    def test_sends_email_with_tls(self, mock_smtp_cls, app):
        """Sends email using STARTTLS when use_tls is True."""
        from app.services.email_service import send_email

        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        config = {
            "server": "smtp.example.com", "port": 587, "use_tls": True,
            "username": "user", "password": "pass",
            "from_address": "noreply@example.com", "from_name": "Test",
        }
        with app.app_context():
            with patch("app.services.email_service._get_smtp_config", return_value=config):
                result = send_email("to@example.com", "Subject", "<p>Body</p>")

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("app.services.email_service.smtplib.SMTP")
    def test_returns_false_on_smtp_error(self, mock_smtp_cls, app):
        """Returns False when SMTP raises an exception."""
        import smtplib
        from app.services.email_service import send_email

        mock_smtp_cls.side_effect = smtplib.SMTPException("Connection failed")

        config = {
            "server": "smtp.example.com", "port": 587, "use_tls": True,
            "username": "", "password": "",
            "from_address": "noreply@example.com", "from_name": "Test",
        }
        with app.app_context():
            with patch("app.services.email_service._get_smtp_config", return_value=config):
                result = send_email("to@example.com", "Subject", "<p>Body</p>")

        assert result is False

    @patch("app.services.email_service.smtplib.SMTP")
    def test_skips_login_when_no_credentials(self, mock_smtp_cls, app):
        """Does not call login() when username/password are empty."""
        from app.services.email_service import send_email

        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        config = {
            "server": "smtp.example.com", "port": 25, "use_tls": False,
            "username": "", "password": "",
            "from_address": "noreply@example.com", "from_name": "Test",
        }
        with app.app_context():
            with patch("app.services.email_service._get_smtp_config", return_value=config):
                result = send_email("to@example.com", "Subject", "<p>Body</p>")

        assert result is True
        mock_server.login.assert_not_called()
        mock_server.starttls.assert_not_called()


class TestSendNotificationEmail:
    """Tests for send_notification_email()."""

    def test_returns_false_when_user_has_no_email(self, app):
        """Returns False when user has no email address."""
        from app.services.email_service import send_notification_email

        user = MagicMock()
        user.email = None
        notification = MagicMock()

        with app.app_context():
            result = send_notification_email(user, notification)
            assert result is False

    def test_returns_false_when_email_disabled(self, app):
        """Returns False when email is not configured."""
        from app.services.email_service import send_notification_email

        user = MagicMock()
        user.email = "user@example.com"
        notification = MagicMock()
        notification.title = "Test"

        with app.app_context():
            with patch("app.services.email_service._get_smtp_config", return_value=None):
                result = send_notification_email(user, notification)
                assert result is False
