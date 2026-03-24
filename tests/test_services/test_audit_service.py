"""Tests for the audit service layer."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.audit_log import AuditLog
from app.services import audit_service
from tests.factories import AuditLogFactory, UserFactory

pytestmark = pytest.mark.unit


class TestLogAction:
    """Tests for audit_service.log_action()."""

    def test_log_action_basic(self, app, db_session):
        entry = audit_service.log_action(
            action="create",
            entity_type="customer",
            entity_id=1,
        )
        assert entry.id is not None
        assert entry.action == "create"
        assert entry.entity_type == "customer"
        assert entry.entity_id == 1

    def test_log_action_with_all_fields(self, app, db_session):
        UserFactory._meta.sqlalchemy_session = db_session
        user = UserFactory()
        db_session.flush()

        entry = audit_service.log_action(
            action="update",
            entity_type="service_order",
            entity_id=42,
            user_id=user.id,
            field_name="status",
            old_value="intake",
            new_value="in_progress",
            ip_address="10.0.0.1",
            user_agent="TestAgent/1.0",
            additional_data='{"note": "rush order"}',
        )
        assert entry.user_id == user.id
        assert entry.field_name == "status"
        assert entry.old_value == "intake"
        assert entry.new_value == "in_progress"
        assert entry.ip_address == "10.0.0.1"
        assert entry.user_agent == "TestAgent/1.0"
        assert entry.additional_data == '{"note": "rush order"}'


class TestGetAuditLogs:
    """Tests for audit_service.get_audit_logs()."""

    def _seed_entries(self, db_session):
        """Create a set of audit log entries for filtering tests."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        UserFactory._meta.sqlalchemy_session = db_session

        user = UserFactory()
        db_session.flush()

        entries = []
        for i in range(5):
            entries.append(AuditLogFactory(
                action="create",
                entity_type="customer",
                entity_id=i + 1,
                user_id=user.id,
            ))
        for i in range(3):
            entries.append(AuditLogFactory(
                action="update",
                entity_type="service_order",
                entity_id=i + 1,
            ))
        db_session.flush()
        return user, entries

    def test_get_audit_logs_no_filter(self, app, db_session):
        user, entries = self._seed_entries(db_session)
        result = audit_service.get_audit_logs()
        assert result.total == 8

    def test_filter_by_entity_type(self, app, db_session):
        user, entries = self._seed_entries(db_session)
        result = audit_service.get_audit_logs(entity_type="customer")
        assert result.total == 5

    def test_filter_by_user(self, app, db_session):
        user, entries = self._seed_entries(db_session)
        result = audit_service.get_audit_logs(user_id=user.id)
        assert result.total == 5

    def test_filter_by_action(self, app, db_session):
        user, entries = self._seed_entries(db_session)
        result = audit_service.get_audit_logs(action="update")
        assert result.total == 3

    def test_filter_by_date_range(self, app, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=1)
        db_session.flush()

        now = datetime.now(timezone.utc)
        result = audit_service.get_audit_logs(
            date_from=now - timedelta(hours=1),
            date_to=now + timedelta(hours=1),
        )
        assert result.total >= 1

    def test_pagination(self, app, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        for i in range(10):
            AuditLogFactory(action="create", entity_type="customer", entity_id=i + 1)
        db_session.flush()

        page1 = audit_service.get_audit_logs(page=1, per_page=3)
        assert len(page1.items) == 3
        assert page1.total == 10
        assert page1.pages == 4

        page2 = audit_service.get_audit_logs(page=2, per_page=3)
        assert len(page2.items) == 3

    def test_empty_results(self, app, db_session):
        result = audit_service.get_audit_logs(entity_type="nonexistent")
        assert result.total == 0
        assert len(result.items) == 0


class TestGetRecentActivity:
    """Tests for audit_service.get_recent_activity()."""

    def test_get_recent_activity(self, app, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        for i in range(25):
            AuditLogFactory(action="create", entity_type="customer", entity_id=i + 1)
        db_session.flush()

        recent = audit_service.get_recent_activity(limit=20)
        assert len(recent) == 20

    def test_get_recent_activity_fewer_than_limit(self, app, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        for i in range(3):
            AuditLogFactory(action="create", entity_type="customer", entity_id=i + 1)
        db_session.flush()

        recent = audit_service.get_recent_activity(limit=20)
        assert len(recent) == 3
