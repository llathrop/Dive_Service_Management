"""Tests for the admin audit log routes."""

import pytest

from tests.factories import AuditLogFactory, UserFactory

pytestmark = pytest.mark.blueprint


class TestAuditLogPage:
    """Tests for GET /admin/audit-log."""

    def test_requires_admin(self, logged_in_client):
        resp = logged_in_client.get("/admin/audit-log")
        assert resp.status_code == 403

    def test_renders_page(self, admin_client):
        resp = admin_client.get("/admin/audit-log")
        assert resp.status_code == 200
        assert b"Audit Log" in resp.data

    def test_filter_by_entity_type(self, admin_client, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=1)
        AuditLogFactory(action="create", entity_type="invoice", entity_id=2)
        db_session.flush()

        resp = admin_client.get("/admin/audit-log?entity_type=customer")
        assert resp.status_code == 200
        assert b"customer" in resp.data

    def test_filter_by_action(self, admin_client, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=1)
        AuditLogFactory(action="delete", entity_type="customer", entity_id=2)
        db_session.flush()

        resp = admin_client.get("/admin/audit-log?action=delete")
        assert resp.status_code == 200
        assert b"delete" in resp.data

    def test_pagination(self, admin_client, db_session):
        AuditLogFactory._meta.sqlalchemy_session = db_session
        for i in range(60):
            AuditLogFactory(action="create", entity_type="customer", entity_id=i + 1)
        db_session.flush()

        resp = admin_client.get("/admin/audit-log?page=1")
        assert resp.status_code == 200
        # Pagination controls should be present
        assert b"Next" in resp.data

    def test_empty_state(self, admin_client):
        resp = admin_client.get("/admin/audit-log")
        assert resp.status_code == 200
        assert b"No audit log entries found" in resp.data
