"""Smoke tests: verify the application starts and is configured correctly."""

import os

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db


pytestmark = pytest.mark.smoke


def test_app_creates(app):
    """The app factory returns a valid Flask application."""
    assert app is not None


def test_app_is_testing(app):
    """The app is running with TESTING=True under TestingConfig."""
    assert app.testing is True


def test_app_has_config(app):
    """Key configuration values are set correctly for the test environment."""
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")
    assert app.config["WTF_CSRF_ENABLED"] is False
    assert app.config["SECURITY_PASSWORD_HASH"] == "plaintext"
    assert app.config["SERVER_NAME"] == "localhost"


def test_app_extensions_loaded(app):
    """All required Flask extensions are initialized on the app."""
    # Flask-SQLAlchemy registers itself under the 'sqlalchemy' key
    assert "sqlalchemy" in app.extensions
    # Flask-Migrate registers under 'migrate'
    assert "migrate" in app.extensions
    # Flask-Security registers under 'security'
    assert "security" in app.extensions


def test_create_app_from_env_var():
    """create_app() with no argument resolves config from DSM_ENV env var."""
    old_env = os.environ.get("DSM_ENV")
    try:
        os.environ["DSM_ENV"] = "testing"
        app = create_app()
        assert app.testing is True
        assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")
    finally:
        if old_env is None:
            os.environ.pop("DSM_ENV", None)
        else:
            os.environ["DSM_ENV"] = old_env


def test_create_app_invalid_env_raises():
    """create_app() with an invalid DSM_ENV raises ValueError."""
    old_env = os.environ.get("DSM_ENV")
    try:
        os.environ["DSM_ENV"] = "nonexistent_environment"
        with pytest.raises(ValueError, match="Unknown environment value"):
            create_app()
    finally:
        if old_env is None:
            os.environ.pop("DSM_ENV", None)
        else:
            os.environ["DSM_ENV"] = old_env
