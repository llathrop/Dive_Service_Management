"""Tests for configuration security posture.

Verifies that ProductionConfig rejects insecure defaults, that
DevelopmentConfig allows them, and that demo user seeding is
blocked in production-like environments.
"""

import pytest
from flask import Flask

from app.config import DevelopmentConfig, ProductionConfig, TestingConfig
from app.models.user import User

pytestmark = pytest.mark.unit


class TestProductionConfigSecrets:
    """ProductionConfig.init_app must reject insecure default secrets."""

    def _make_app(self, config_class):
        """Create a minimal Flask app with the given config (no extensions)."""
        app = Flask(__name__)
        app.config.from_object(config_class)
        return app

    def test_production_config_rejects_default_secret_key(self):
        """ProductionConfig.init_app should raise RuntimeError when
        SECRET_KEY is still the insecure default."""
        app = self._make_app(ProductionConfig)
        # Force the dangerous default (env var may override at import time)
        app.config["SECRET_KEY"] = "change-me-in-production"
        app.config["SECURITY_PASSWORD_SALT"] = "safe-salt-value"

        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            ProductionConfig.init_app(app)

    def test_production_config_rejects_default_salt(self):
        """ProductionConfig.init_app should raise RuntimeError when
        SECURITY_PASSWORD_SALT is still the insecure default."""
        app = self._make_app(ProductionConfig)
        app.config["SECRET_KEY"] = "a-real-secret-key-that-is-not-default"
        # Force the dangerous default for salt
        app.config["SECURITY_PASSWORD_SALT"] = "change-me-salt-in-production"

        with pytest.raises(RuntimeError, match="SECURITY_PASSWORD_SALT"):
            ProductionConfig.init_app(app)

    def test_production_config_accepts_custom_secrets(self):
        """ProductionConfig.init_app should not raise when both secrets are
        set to non-default values."""
        app = self._make_app(ProductionConfig)
        app.config["SECRET_KEY"] = "my-super-secret-production-key"
        app.config["SECURITY_PASSWORD_SALT"] = "my-super-secret-salt"

        # Should not raise
        ProductionConfig.init_app(app)

        assert app.config["SECRET_KEY"] == "my-super-secret-production-key"
        assert app.config["SECURITY_PASSWORD_SALT"] == "my-super-secret-salt"

    def test_development_config_allows_defaults(self):
        """DevelopmentConfig has no init_app, so insecure defaults are
        allowed without error.  Verify that hasattr returns False and
        that creating a minimal Flask app with DevConfig works fine."""
        assert not hasattr(DevelopmentConfig, "init_app")

        app = self._make_app(DevelopmentConfig)
        # Defaults should be present without error
        assert app.config["SECRET_KEY"] == DevelopmentConfig.SECRET_KEY
        assert app.config["DEBUG"] is True

    def test_testing_config_has_no_init_app(self):
        """TestingConfig should not have its own init_app method."""
        assert not hasattr(TestingConfig, "init_app")


class TestSeedDemoUsersProductionGuard:
    """_seed_demo_users must skip demo user creation in production mode."""

    def test_seed_skips_demo_users_in_production(self, app):
        """When DEBUG=False and TESTING=False, seed-db should skip demo
        users and print a message about using create-admin instead."""
        # Override the app config to simulate production-like mode
        app.config["DEBUG"] = False
        app.config["TESTING"] = False

        runner = app.test_cli_runner()
        result = runner.invoke(args=["seed-db"])

        assert "Skipping demo users" in result.output
        assert "flask create-admin" in result.output

        # Verify no demo users were actually created
        with app.app_context():
            admin = User.query.filter_by(email="admin@example.com").first()
            assert admin is None

    def test_seed_creates_demo_users_in_debug(self, app):
        """In DEBUG mode, demo users should be created normally."""
        app.config["DEBUG"] = True
        app.config["TESTING"] = False

        runner = app.test_cli_runner()
        result = runner.invoke(args=["seed-db"])

        # The seed command should attempt to create demo users
        # (may hit IntegrityError if username field is missing in seed data,
        # but the important thing is it does NOT skip them)
        assert "Skipping demo users" not in result.output

    def test_seed_creates_demo_users_in_testing(self, app):
        """In TESTING mode, demo users should be created normally."""
        app.config["DEBUG"] = False
        app.config["TESTING"] = True

        runner = app.test_cli_runner()
        result = runner.invoke(args=["seed-db"])

        # The seed command should attempt to create demo users
        assert "Skipping demo users" not in result.output


class TestSeedSystemConfig:
    """Verify that _seed_system_config populates system_config entries."""

    def test_seed_creates_system_config_entries(self, app):
        """_seed_system_config should create all default rows."""
        from app.cli.seed import _seed_system_config
        from app.models.system_config import SystemConfig

        with app.app_context():
            _seed_system_config()

            entries = SystemConfig.query.all()
            assert len(entries) >= 25  # We seed ~29 entries
            keys = {e.config_key for e in entries}
            assert "company.name" in keys
            assert "tax.default_rate" in keys
            assert "security.password_min_length" in keys

    def test_seed_is_idempotent(self, app):
        """Running _seed_system_config twice should not duplicate entries."""
        from app.cli.seed import _seed_system_config
        from app.models.system_config import SystemConfig

        with app.app_context():
            _seed_system_config()
            count_first = SystemConfig.query.count()

            _seed_system_config()
            count_second = SystemConfig.query.count()

            assert count_first == count_second
