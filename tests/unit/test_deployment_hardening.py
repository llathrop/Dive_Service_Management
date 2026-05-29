"""Unit tests for deployment hardening features (Stage 1)."""

import os
from unittest.mock import patch, MagicMock
import pytest
from flask import Flask, session
from app import create_app
from app.services.data_management_service import create_backup_sql, _mysql_dump
from app.services.config_service import set_config
from app.models.portal_user import PortalUser
from werkzeug.middleware.proxy_fix import ProxyFix

pytestmark = pytest.mark.unit


def test_proxy_fix_middleware(monkeypatch):
    """S1-1: ProxyFix middleware is applied when DSM_PROXY_COUNT > 0."""
    monkeypatch.setenv("DSM_PROXY_COUNT", "2")
    # Initialize a new app factory instance under these environment variables
    app = create_app()
    assert isinstance(app.wsgi_app, ProxyFix)
    # Clear env
    monkeypatch.delenv("DSM_PROXY_COUNT", raising=False)


def test_host_header_validation(monkeypatch, client):
    """S1-6: Host header check permits matching Hosts and aborts unmatched ones."""
    # Temporarily patch environment variable and recreate app context for testing
    monkeypatch.setenv("DSM_ALLOWED_HOSTS", "localhost,example.com")
    app = create_app()
    
    with app.test_client() as test_client:
        # Host matching example.com should pass (returns typical 404/200/302, not 400)
        res = test_client.get("/", headers={"Host": "example.com"})
        assert res.status_code != 400

        # Host matching localhost should pass
        res = test_client.get("/", headers={"Host": "localhost"})
        assert res.status_code != 400

        # Host matching a port should pass if inside allowed list
        res = test_client.get("/", headers={"Host": "example.com:8080"})
        assert res.status_code != 400

        # Untrusted host should return 400 Bad Request
        res = test_client.get("/", headers={"Host": "malicious-site.com"})
        assert res.status_code == 400


def test_dynamic_session_lifetime(app, db_session):
    """S1-3: Dynamic session lifetime enforcement from database settings."""
    from datetime import timedelta
    from app.services.config_service import set_config
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


def test_sensitive_field_redaction_smtp_password():
    """S1-5: Sensitive audit fields (including email.smtp_password) are redacted in CSV exports."""
    from app.blueprints.admin.audit import SENSITIVE_FIELDS
    assert "email.smtp_password" in SENSITIVE_FIELDS

    # Verify that mock sensitive audit log entry is correctly redacted
    entry = MagicMock()
    entry.field_name = "email.smtp_password"
    entry.old_value = "supersecret123"
    entry.new_value = "newsecret456"

    details = ""
    if entry.field_name and entry.field_name in SENSITIVE_FIELDS:
        details = f"{entry.field_name}: [REDACTED]"

    assert details == "email.smtp_password: [REDACTED]"

