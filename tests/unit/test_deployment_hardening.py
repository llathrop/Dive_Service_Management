"""Unit and integration tests for deployment hardening features (Stage 1)."""

import os
from datetime import timedelta
from unittest.mock import patch, MagicMock
import pytest
from flask import Flask, session
from app import create_app
from app.services.data_management_service import create_backup_sql, _mysql_dump
from app.services.config_service import set_config
from app.models.portal_user import PortalUser
from werkzeug.middleware.proxy_fix import ProxyFix

pytestmark = pytest.mark.unit


def test_proxy_fix_middleware_applied(monkeypatch):
    """S1-1: ProxyFix middleware is applied when DSM_PROXY_COUNT > 0."""
    monkeypatch.setenv("DSM_PROXY_COUNT", "2")
    app = create_app()
    assert isinstance(app.wsgi_app, ProxyFix)
    monkeypatch.delenv("DSM_PROXY_COUNT", raising=False)


def test_proxy_fix_middleware_integration(monkeypatch):
    """S1-1: ProxyFix middleware is applied and correctly parses forwarded client IP and scheme."""
    monkeypatch.setenv("DSM_PROXY_COUNT", "1")
    app = create_app()
    
    # Register a temporary test route to inspect the request context remote_addr & scheme
    @app.route("/test-ip")
    def test_ip_route():
        from flask import request
        return {"remote_addr": request.remote_addr, "scheme": request.scheme}

    with app.test_client() as client:
        # Send a request with X-Forwarded-For and X-Forwarded-Proto headers
        res = client.get("/test-ip", headers={
            "X-Forwarded-For": "203.0.113.195",
            "X-Forwarded-Proto": "https"
        })
        assert res.status_code == 200
        data = res.get_json()
        # Verify that ProxyFix correctly intercepted the WSGI environment variables and updated remote_addr
        assert data["remote_addr"] == "203.0.113.195"
        assert data["scheme"] == "https"

    monkeypatch.delenv("DSM_PROXY_COUNT", raising=False)


def test_host_header_validation(monkeypatch):
    """S1-6: Host header check permits matching Hosts and aborts unmatched ones with 400 Bad Request."""
    monkeypatch.setenv("DSM_ALLOWED_HOSTS", "localhost,example.com")
    app = create_app()
    
    with app.test_client() as test_client:
        # Host matching example.com should pass (returns typical 404/200/302, not 400)
        res = test_client.get("/health/live", headers={"Host": "example.com"})
        assert res.status_code != 400

        # Host matching localhost should pass
        res = test_client.get("/health/live", headers={"Host": "localhost"})
        assert res.status_code != 400

        # Host matching a port should pass if inside allowed list
        res = test_client.get("/health/live", headers={"Host": "example.com:8080"})
        assert res.status_code != 400

        # Untrusted host should return 400 Bad Request
        res = test_client.get("/health/live", headers={"Host": "malicious-site.com"})
        assert res.status_code == 400

    monkeypatch.delenv("DSM_ALLOWED_HOSTS", raising=False)


def test_host_header_validation_bypass(monkeypatch):
    """S1-6: Host header check is completely bypassed if DSM_ALLOWED_HOSTS is empty or '*'."""
    # Test wildcard bypass
    monkeypatch.setenv("DSM_ALLOWED_HOSTS", "*")
    app = create_app()
    with app.test_client() as test_client:
        res = test_client.get("/health/live", headers={"Host": "malicious-site.com"})
        assert res.status_code == 200

    # Test empty bypass
    monkeypatch.setenv("DSM_ALLOWED_HOSTS", "")
    app = create_app()
    with app.test_client() as test_client:
        res = test_client.get("/health/live", headers={"Host": "malicious-site.com"})
        assert res.status_code == 200

    monkeypatch.delenv("DSM_ALLOWED_HOSTS", raising=False)


def test_dynamic_session_lifetime(app, db_session):
    """S1-3: Dynamic session lifetime enforcement from database settings."""
    from app.models.system_config import SystemConfig

    with app.app_context():
        # Create/seed the SystemConfig row in DB first if not exists
        row = SystemConfig.query.filter_by(config_key="security.session_lifetime_hours").first()
        if not row:
            row = SystemConfig(
                config_key="security.session_lifetime_hours",
                config_type="integer",
                category="security",
                description="Session lifetime in hours"
            )
            db_session.add(row)
            db_session.commit()

        # Set config to 4 hours in DB
        set_config("security.session_lifetime_hours", 4)
        db_session.commit()

        # Simulate a request by using the test client
        with app.test_client() as client:
            client.get("/")
            assert app.permanent_session_lifetime == timedelta(hours=4)

        # Set config to 12 hours in DB
        set_config("security.session_lifetime_hours", 12)
        db_session.commit()

        with app.test_client() as client:
            client.get("/")
            assert app.permanent_session_lifetime == timedelta(hours=12)


@patch("subprocess.run")
def test_secure_database_backup(mock_run, app):
    """S1-4: Database password is not passed to mariadb-dump CLI, but through MYSQL_PWD."""
    mock_run.return_value = MagicMock(stdout="SUCCESSFUL DUMP", stderr="")

    with app.app_context():
        # Set config database URL
        app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+mysqldb://dsm_user:my_secret_password@localhost:3306/dsm_db"
        
        # Trigger database dump
        from app.services.data_management_service import _mysql_dump
        _mysql_dump()

        # Assert subprocess execution characteristics
        assert mock_run.called
        args, kwargs = mock_run.call_args
        
        # Verify the command arguments
        cmd = args[0]
        assert "mariadb-dump" in cmd
        assert "--host=localhost" in cmd
        assert "--port=3306" in cmd
        assert "--user=dsm_user" in cmd
        
        # Ensure password is NOT in the CLI args
        for arg in cmd:
            assert "my_secret_password" not in arg
            assert "--password" not in arg

        # Verify MYSQL_PWD env variable exists and has the correct password
        env = kwargs.get("env")
        assert env is not None
        assert env.get("MYSQL_PWD") == "my_secret_password"


def test_sensitive_field_redaction_smtp_password_integration(app, db_session):
    """S1-5: Sensitive audit fields (including email.smtp_password) are redacted in real streaming CSV exports."""
    from app.models.user import User
    from app.models.audit_log import AuditLog
    from flask_security import hash_password
    from tests._fixtures import _login_client

    with app.app_context():
        # 1. Create an admin user to perform the request
        user_datastore = app.extensions["security"].datastore
        admin_role = user_datastore.find_or_create_role(
            name="admin", description="Full system access"
        )
        
        admin_user = user_datastore.find_user(email="admin_audit@example.com")
        if not admin_user:
            admin_user = user_datastore.create_user(
                username="admin_audit",
                email="admin_audit@example.com",
                password=hash_password("adminpassword123"),
                first_name="Admin",
                last_name="Audit",
            )
            user_datastore.add_role_to_user(admin_user, admin_role)
            db_session.commit()

        # 2. Insert a real sensitive audit log entry into the database
        audit_entry = AuditLog(
            action="update",
            entity_type="system",
            entity_id=1,
            user_id=admin_user.id,
            field_name="email.smtp_password",
            old_value="plaintext_smtp_password_123",
            new_value="new_smtp_password_456",
        )
        db_session.add(audit_entry)
        db_session.commit()

        # 3. Log in the client as the admin user
        client = _login_client(app, "admin_audit@example.com", "adminpassword123")

        # 4. Request the real CSV export stream
        res = client.get("/admin/audit-log/export")
        assert res.status_code == 200
        assert res.mimetype == "text/csv"

        # 5. Read response content bytes and decode
        csv_data = res.data.decode("utf-8-sig")

        # 6. Verify that the plaintext password is redacted and DOES NOT appear in the CSV output
        assert "plaintext_smtp_password_123" not in csv_data
        assert "new_smtp_password_456" not in csv_data
        assert "email.smtp_password: [REDACTED]" in csv_data
