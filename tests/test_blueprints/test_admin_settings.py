"""Tests for the admin settings routes."""

import pytest

from app.cli.seed import _seed_system_config
from app.models.system_config import SystemConfig
from app.services import config_service

pytestmark = pytest.mark.blueprint


class TestSettingsPage:
    """Tests for GET /admin/settings."""

    def test_settings_requires_login(self, client):
        resp = client.get("/admin/settings")
        # SECURITY_UNAUTHORIZED_VIEW=None returns 403 for unauthenticated
        assert resp.status_code in (302, 308, 403)

    def test_settings_requires_admin_role(self, logged_in_client):
        resp = logged_in_client.get("/admin/settings")
        assert resp.status_code == 403

    def test_settings_renders_for_admin(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.get("/admin/settings")
        assert resp.status_code == 200
        assert b"System Settings" in resp.data
        assert b"Company" in resp.data

    def test_settings_default_tab_is_company(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.get("/admin/settings")
        assert resp.status_code == 200
        assert b"Company Settings" in resp.data

    def test_settings_tab_parameter(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.get("/admin/settings?tab=security")
        assert resp.status_code == 200
        assert b"Security Settings" in resp.data

    def test_settings_invalid_tab_defaults_to_company(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.get("/admin/settings?tab=invalid_tab")
        assert resp.status_code == 200
        assert b"Company Settings" in resp.data

    def test_settings_all_tabs_render(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        for tab in ["company", "service", "invoice_tax", "display", "notification", "security"]:
            resp = admin_client.get(f"/admin/settings?tab={tab}")
            assert resp.status_code == 200, f"Tab {tab} failed"


class TestSettingsSave:
    """Tests for POST /admin/settings."""

    def test_save_company_settings(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.post(
            "/admin/settings?tab=company",
            data={
                "tab": "company",
                "company_name": "Test Dive Shop",
                "company_address": "123 Main St",
                "company_phone": "555-1234",
                "company_email": "info@test.com",
                "company_website": "https://test.com",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Settings updated" in resp.data
        with app.app_context():
            assert config_service.get_config("company.name") == "Test Dive Shop"

    def test_save_service_settings(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.post(
            "/admin/settings?tab=service",
            data={
                "tab": "service",
                "order_prefix": "WO",
                "default_labor_rate": "95.00",
                "rush_fee_default": "75.00",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Settings updated" in resp.data
        with app.app_context():
            assert config_service.get_config("service.order_prefix") == "WO"

    def test_save_invoice_tax_settings(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.post(
            "/admin/settings?tab=invoice_tax",
            data={
                "tab": "invoice_tax",
                "invoice_prefix": "INV",
                "default_terms": "Net 15",
                "default_due_days": "15",
                "footer_text": "Thank you!",
                "tax_rate": "0.0825",
                "tax_label": "Sales Tax",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            assert config_service.get_config("invoice.default_terms") == "Net 15"

    def test_save_display_settings(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.post(
            "/admin/settings?tab=display",
            data={
                "tab": "display",
                "date_format": "%m/%d/%Y",
                "currency_symbol": "$",
                "currency_code": "USD",
                "pagination_size": "50",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            assert config_service.get_config("display.pagination_size") == 50

    def test_save_notification_settings(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.post(
            "/admin/settings?tab=notification",
            data={
                "tab": "notification",
                "low_stock_check_hours": "12",
                "overdue_check_time": "09:00",
                "retention_days": "60",
                "order_due_warning_days": "3",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            assert config_service.get_config("notification.retention_days") == 60

    def test_save_security_settings(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.post(
            "/admin/settings?tab=security",
            data={
                "tab": "security",
                "password_min_length": "12",
                "lockout_attempts": "3",
                "lockout_duration_minutes": "30",
                "session_lifetime_hours": "12",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            assert config_service.get_config("security.password_min_length") == 12

    def test_save_validation_error(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.post(
            "/admin/settings?tab=display",
            data={
                "tab": "display",
                "date_format": "",  # required field
                "currency_symbol": "$",
                "currency_code": "USD",
                "pagination_size": "50",
            },
        )
        # Should re-render the form with errors (not redirect)
        assert resp.status_code == 200

    def test_save_requires_admin(self, logged_in_client, app):
        resp = logged_in_client.post(
            "/admin/settings?tab=company",
            data={"tab": "company", "company_name": "Hacked"},
        )
        assert resp.status_code == 403


class TestSettingsEnvLocking:
    """Tests for ENV-locked settings display."""

    def test_env_locked_field_shows_badge(self, admin_client, app, monkeypatch):
        with app.app_context():
            _seed_system_config()
        monkeypatch.setenv("DSM_COMPANY_NAME", "ENV Company")
        resp = admin_client.get("/admin/settings?tab=company")
        assert resp.status_code == 200
        assert b"ENV" in resp.data
