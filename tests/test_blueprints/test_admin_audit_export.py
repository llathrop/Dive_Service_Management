"""Tests for the admin audit log export endpoint."""

import pytest

from tests.factories import AuditLogFactory


class TestAuditLogExport:
    """Tests for GET /admin/audit-log/export."""

    def test_requires_admin(self, logged_in_client):
        """Non-admin users should get 403."""
        resp = logged_in_client.get("/admin/audit-log/export")
        assert resp.status_code == 403

    def test_viewer_gets_403(self, viewer_client):
        """Viewer role should get 403."""
        resp = viewer_client.get("/admin/audit-log/export")
        assert resp.status_code == 403

    def test_admin_can_export(self, admin_client, db_session):
        """Admin should get a 200 CSV response."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=1)
        db_session.flush()

        resp = admin_client.get("/admin/audit-log/export")
        assert resp.status_code == 200

    def test_response_is_csv(self, admin_client, db_session):
        """Response should have CSV content type and attachment disposition."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=1)
        db_session.flush()

        resp = admin_client.get("/admin/audit-log/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type
        assert "attachment" in resp.headers.get("Content-Disposition", "")
        assert "audit_log.csv" in resp.headers.get("Content-Disposition", "")

    def test_csv_contains_expected_headers(self, admin_client, db_session):
        """CSV output should contain the expected column headers."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=1)
        db_session.flush()

        resp = admin_client.get("/admin/audit-log/export")
        assert resp.status_code == 200

        # Decode and check header row (skip BOM)
        text = resp.data.decode("utf-8-sig")
        lines = text.strip().split("\n")
        assert len(lines) >= 2  # header + at least one data row
        header_line = lines[0]
        for col in ["Timestamp", "User", "Action", "Entity Type", "Entity ID", "Details"]:
            assert col in header_line

    def test_csv_contains_data_rows(self, admin_client, db_session):
        """CSV should contain data matching the audit log entries."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=42)
        AuditLogFactory(action="delete", entity_type="invoice", entity_id=7)
        db_session.flush()

        resp = admin_client.get("/admin/audit-log/export")
        text = resp.data.decode("utf-8-sig")
        lines = text.strip().split("\n")
        # header + 2 data rows
        assert len(lines) == 3

    def test_export_respects_entity_type_filter(self, admin_client, db_session):
        """Export should filter by entity_type when provided."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(action="create", entity_type="customer", entity_id=1)
        AuditLogFactory(action="create", entity_type="invoice", entity_id=2)
        db_session.flush()

        resp = admin_client.get("/admin/audit-log/export?entity_type=customer")
        text = resp.data.decode("utf-8-sig")
        lines = text.strip().split("\n")
        # header + 1 matching row
        assert len(lines) == 2
        assert "customer" in lines[1]
        assert "invoice" not in lines[1]

    def test_export_empty_returns_headers_only(self, admin_client):
        """Export with no data should return only the header row."""
        resp = admin_client.get("/admin/audit-log/export")
        assert resp.status_code == 200
        text = resp.data.decode("utf-8-sig")
        lines = text.strip().split("\n")
        assert len(lines) == 1  # header only
        assert "Timestamp" in lines[0]

    def test_export_redacts_sensitive_fields(self, admin_client, db_session):
        """Sensitive fields like password_hash should be redacted in export."""
        AuditLogFactory._meta.sqlalchemy_session = db_session
        AuditLogFactory(
            action="update",
            entity_type="user",
            entity_id=1,
            field_name="password_hash",
            old_value="$argon2id$old_hash",
            new_value="$argon2id$new_hash",
        )
        AuditLogFactory(
            action="update",
            entity_type="user",
            entity_id=1,
            field_name="email",
            old_value="old@example.com",
            new_value="new@example.com",
        )
        db_session.flush()

        resp = admin_client.get("/admin/audit-log/export")
        text = resp.data.decode("utf-8-sig")
        # Sensitive hash values must not appear
        assert "$argon2id$" not in text
        assert "[REDACTED]" in text
        # Non-sensitive field should still show values
        assert "old@example.com" in text
        assert "new@example.com" in text
