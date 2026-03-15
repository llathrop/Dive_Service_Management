"""Tests for the AuditLog model."""

import pytest

from app.models.audit_log import AuditLog
from tests.factories import AuditLogFactory, UserFactory


class TestAuditLogModel:
    """Unit tests for the AuditLog model."""

    def test_create_audit_log(self, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        entry = AuditLogFactory(
            action="create",
            entity_type="customer",
            entity_id=1,
        )
        db_session.flush()
        assert entry.id is not None
        assert entry.action == "create"
        assert entry.entity_type == "customer"
        assert entry.entity_id == 1

    def test_required_fields_action(self, db_session):
        """action, entity_type, and entity_id are required."""
        entry = AuditLog(entity_type="customer", entity_id=1)
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.flush()

    def test_required_fields_entity_type(self, db_session):
        entry = AuditLog(action="create", entity_id=1)
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.flush()

    def test_required_fields_entity_id(self, db_session):
        entry = AuditLog(action="create", entity_type="customer")
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.flush()

    def test_user_relationship(self, db_session):
        UserFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory._meta.sqlalchemy_session = db_session
        user = UserFactory()
        db_session.flush()
        entry = AuditLogFactory(
            action="update",
            entity_type="service_order",
            entity_id=42,
            user_id=user.id,
        )
        db_session.flush()
        assert entry.user is not None
        assert entry.user.id == user.id
        assert entry in user.audit_logs

    def test_nullable_fields(self, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        entry = AuditLogFactory(
            action="delete",
            entity_type="invoice",
            entity_id=5,
            user_id=None,
            field_name=None,
            old_value=None,
            new_value=None,
            ip_address=None,
            user_agent=None,
            additional_data=None,
        )
        db_session.flush()
        assert entry.id is not None
        assert entry.user_id is None
        assert entry.field_name is None
        assert entry.old_value is None
        assert entry.new_value is None

    def test_all_fields_populated(self, db_session):
        UserFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory._meta.sqlalchemy_session = db_session
        user = UserFactory()
        db_session.flush()
        entry = AuditLogFactory(
            action="update",
            entity_type="customer",
            entity_id=10,
            user_id=user.id,
            field_name="email",
            old_value="old@example.com",
            new_value="new@example.com",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            additional_data='{"reason": "correction"}',
        )
        db_session.flush()
        assert entry.field_name == "email"
        assert entry.old_value == "old@example.com"
        assert entry.new_value == "new@example.com"
        assert entry.ip_address == "192.168.1.1"
        assert entry.user_agent == "Mozilla/5.0"
        assert entry.additional_data == '{"reason": "correction"}'

    def test_action_values(self, db_session):
        """Various action strings are accepted."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        for action in ["create", "update", "delete", "restore", "login", "logout", "export", "status_change"]:
            entry = AuditLogFactory(action=action, entity_type="test", entity_id=1)
            db_session.flush()
            assert entry.action == action

    def test_repr(self, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        entry = AuditLogFactory(action="create", entity_type="customer", entity_id=99)
        assert "create" in repr(entry)
        assert "customer" in repr(entry)
        assert "99" in repr(entry)
