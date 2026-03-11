"""Tests for the SystemConfig model."""

import json

import pytest

from app.models.system_config import SystemConfig, VALID_CONFIG_TYPES, VALID_CATEGORIES
from tests.factories import SystemConfigFactory


class TestSystemConfigModel:
    """Unit tests for the SystemConfig model."""

    def test_create_string_config(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(
            config_key="company.name",
            config_value="Test Shop",
            config_type="string",
            category="company",
        )
        db_session.flush()
        assert cfg.id is not None
        assert cfg.typed_value == "Test Shop"

    def test_typed_value_integer(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(
            config_key="display.pagination_size",
            config_value="25",
            config_type="integer",
        )
        db_session.flush()
        assert cfg.typed_value == 25
        assert isinstance(cfg.typed_value, int)

    def test_typed_value_float(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(
            config_key="tax.default_rate",
            config_value="0.0825",
            config_type="float",
        )
        db_session.flush()
        assert cfg.typed_value == pytest.approx(0.0825)

    def test_typed_value_boolean_true(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(
            config_key="test.bool_true",
            config_value="true",
            config_type="boolean",
        )
        db_session.flush()
        assert cfg.typed_value is True

    def test_typed_value_boolean_false(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(
            config_key="test.bool_false",
            config_value="false",
            config_type="boolean",
        )
        db_session.flush()
        assert cfg.typed_value is False

    def test_typed_value_json(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        data = {"key": "value", "list": [1, 2, 3]}
        cfg = SystemConfigFactory(
            config_key="test.json_val",
            config_value=json.dumps(data),
            config_type="json",
        )
        db_session.flush()
        assert cfg.typed_value == data

    def test_typed_value_none(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(
            config_key="test.none_val",
            config_value=None,
            config_type="string",
        )
        db_session.flush()
        assert cfg.typed_value is None

    def test_typed_value_setter_string(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(config_key="test.set_str", config_type="string")
        cfg.typed_value = "new value"
        assert cfg.config_value == "new value"

    def test_typed_value_setter_boolean(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(config_key="test.set_bool", config_type="boolean")
        cfg.typed_value = True
        assert cfg.config_value == "true"
        cfg.typed_value = False
        assert cfg.config_value == "false"

    def test_typed_value_setter_json(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(config_key="test.set_json", config_type="json")
        data = {"a": 1}
        cfg.typed_value = data
        assert cfg.config_value == json.dumps(data)

    def test_typed_value_setter_none(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(config_key="test.set_none", config_type="string")
        cfg.typed_value = None
        assert cfg.config_value is None

    def test_unique_config_key(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        SystemConfigFactory(config_key="unique.key")
        db_session.flush()
        with pytest.raises(Exception):
            SystemConfigFactory(config_key="unique.key")
            db_session.flush()

    def test_repr(self, db_session):
        SystemConfigFactory._meta.sqlalchemy_session = db_session
        cfg = SystemConfigFactory(config_key="test.repr", config_value="val")
        assert "test.repr" in repr(cfg)

    def test_valid_config_types_constant(self):
        assert "string" in VALID_CONFIG_TYPES
        assert "integer" in VALID_CONFIG_TYPES
        assert "float" in VALID_CONFIG_TYPES
        assert "boolean" in VALID_CONFIG_TYPES
        assert "json" in VALID_CONFIG_TYPES

    def test_valid_categories_constant(self):
        assert "company" in VALID_CATEGORIES
        assert "invoice" in VALID_CATEGORIES
        assert "security" in VALID_CATEGORIES
