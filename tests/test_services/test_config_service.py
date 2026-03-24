"""Tests for the config_service module."""

import os

import pytest

from app.models.system_config import SystemConfig
from app.services import config_service
from tests.factories import SystemConfigFactory

pytestmark = pytest.mark.unit


class TestGetConfig:
    """Tests for get_config()."""

    def test_get_existing_string(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(
            config_key="company.name",
            config_value="Test Shop",
            config_type="string",
            category="company",
        )
        db_session.flush()
        assert config_service.get_config("company.name") == "Test Shop"

    def test_get_existing_integer(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(
            config_key="display.pagination_size",
            config_value="50",
            config_type="integer",
            category="display",
        )
        db_session.flush()
        assert config_service.get_config("display.pagination_size") == 50

    def test_get_nonexistent_returns_default(self, db_session):
        result = config_service.get_config("nonexistent.key", default="fallback")
        assert result == "fallback"

    def test_get_nonexistent_returns_none(self, db_session):
        result = config_service.get_config("nonexistent.key")
        assert result is None

    def test_env_override(self, db_session, monkeypatch):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(
            config_key="company.name",
            config_value="DB Value",
            config_type="string",
            category="company",
        )
        db_session.flush()
        monkeypatch.setenv("DSM_COMPANY_NAME", "ENV Value")
        assert config_service.get_config("company.name") == "ENV Value"

    def test_env_override_with_type_coercion(self, db_session, monkeypatch):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(
            config_key="display.pagination_size",
            config_value="25",
            config_type="integer",
            category="display",
        )
        db_session.flush()
        monkeypatch.setenv("DSM_PAGINATION_SIZE", "100")
        result = config_service.get_config("display.pagination_size")
        assert result == 100
        assert isinstance(result, int)

    def test_env_not_set_uses_db(self, db_session, monkeypatch):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(
            config_key="company.name",
            config_value="DB Value",
            config_type="string",
            category="company",
        )
        db_session.flush()
        monkeypatch.delenv("DSM_COMPANY_NAME", raising=False)
        assert config_service.get_config("company.name") == "DB Value"


class TestSetConfig:
    """Tests for set_config()."""

    def test_set_existing_value(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(
            config_key="company.name",
            config_value="Old Name",
            config_type="string",
            category="company",
        )
        db_session.flush()
        result = config_service.set_config("company.name", "New Name")
        assert result.config_value == "New Name"
        assert config_service.get_config("company.name") == "New Name"

    def test_set_with_user_id(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(
            config_key="company.phone",
            config_value="",
            config_type="string",
            category="company",
        )
        db_session.flush()
        result = config_service.set_config("company.phone", "555-1234", user_id=1)
        assert result.updated_by == 1

    def test_set_nonexistent_raises_key_error(self, db_session):
        with pytest.raises(KeyError, match="does not exist"):
            config_service.set_config("nonexistent.key", "value")

    def test_set_env_locked_raises_value_error(self, db_session, monkeypatch):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(
            config_key="company.name",
            config_value="DB Value",
            config_type="string",
            category="company",
        )
        db_session.flush()
        monkeypatch.setenv("DSM_COMPANY_NAME", "ENV Value")
        with pytest.raises(ValueError, match="locked by environment variable"):
            config_service.set_config("company.name", "Blocked")


class TestIsEnvLocked:
    """Tests for is_env_locked()."""

    def test_locked_when_env_set(self, monkeypatch):
        monkeypatch.setenv("DSM_COMPANY_NAME", "anything")
        assert config_service.is_env_locked("company.name") is True

    def test_not_locked_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("DSM_COMPANY_NAME", raising=False)
        assert config_service.is_env_locked("company.name") is False

    def test_not_locked_for_unmapped_key(self):
        assert config_service.is_env_locked("tax.default_rate") is False


class TestGetAllInCategory:
    """Tests for get_all_in_category()."""

    def test_returns_all_in_category(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(config_key="company.name", category="company")
        SystemConfigFactory(config_key="company.phone", category="company")
        SystemConfigFactory(config_key="tax.rate", category="tax")
        db_session.flush()

        results = config_service.get_all_in_category("company")
        assert len(results) == 2
        keys = [r.config_key for r in results]
        assert "company.name" in keys
        assert "company.phone" in keys

    def test_empty_category(self, db_session):
        results = config_service.get_all_in_category("nonexistent")
        assert results == []


class TestBulkSet:
    """Tests for bulk_set()."""

    def test_bulk_set_multiple(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(config_key="company.name", config_value="Old", config_type="string", category="company")
        SystemConfigFactory(config_key="company.phone", config_value="", config_type="string", category="company")
        db_session.flush()

        count = config_service.bulk_set({
            "company.name": "New Name",
            "company.phone": "555-0000",
        })
        assert count == 2
        assert config_service.get_config("company.name") == "New Name"
        assert config_service.get_config("company.phone") == "555-0000"

    def test_bulk_set_skips_env_locked(self, db_session, monkeypatch):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(config_key="company.name", config_value="Old", config_type="string", category="company")
        SystemConfigFactory(config_key="company.phone", config_value="", config_type="string", category="company")
        db_session.flush()
        monkeypatch.setenv("DSM_COMPANY_NAME", "ENV")

        count = config_service.bulk_set({
            "company.name": "Blocked",
            "company.phone": "555-0000",
        })
        assert count == 1
        # DB value unchanged for locked key
        row = SystemConfig.query.filter_by(config_key="company.name").first()
        assert row.config_value == "Old"

    def test_bulk_set_skips_nonexistent_keys(self, db_session):
        count = config_service.bulk_set({"nonexistent.key": "value"})
        assert count == 0
